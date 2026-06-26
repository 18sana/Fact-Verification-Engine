import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import mlflow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import SkepticAgent
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.models import AdversarialEvalRun, EvaluationResult, Experiment
from app.domain.models import EvaluationMetrics
from app.services.training import TrainingDatasetBuilder
from app.training.finetune import run_qlora_finetuning

logger = get_logger(__name__)


def _mlflow_run_id(name: str, settings: Settings) -> Optional[str]:
    """Start an MLflow run when the tracking server is reachable; otherwise skip."""
    try:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(settings.mlflow_experiment_name)
        with mlflow.start_run(run_name=name) as run:
            return run.info.run_id
    except Exception as e:
        logger.warning("mlflow_unavailable", error=str(e), uri=settings.mlflow_tracking_uri)
        return None


def _mlflow_log_run(run_id: str, settings: Settings, *, params: Optional[dict] = None, metrics: Optional[dict] = None) -> None:
    """Log params/metrics to an existing MLflow run; no-op if unreachable."""
    try:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        with mlflow.start_run(run_id=run_id):
            if params:
                mlflow.log_params(params)
            if metrics:
                for key, value in metrics.items():
                    mlflow.log_metric(key, value)
    except Exception as e:
        logger.warning("mlflow_log_failed", error=str(e), run_id=run_id)


class AdversarialTestGenerator:
    """Generate difficult factual claims for continuous Skeptic evaluation."""

    TEMPLATES = [
        ("{entity} won {event} in {wrong_year}", "subtle_date_change"),
        ("{wrong_entity} won {event} in {year}", "entity_swap"),
        ("{entity} almost won {event} in {year}", "misleading_wording"),
        ("{entity} won {event} in {year} but lost the final", "contradictory"),
        ("{entity} may have won {event} in {year}", "partially_true"),
    ]

    SEED_CLAIMS = [
        {"entity": "India", "event": "Cricket World Cup", "year": "2011", "wrong_year": "2007", "wrong_entity": "Australia"},
        {"entity": "Australia", "event": "Cricket World Cup", "year": "2015", "wrong_year": "2011", "wrong_entity": "India"},
        {"entity": "England", "event": "Cricket World Cup", "year": "2019", "wrong_year": "2015", "wrong_entity": "New Zealand"},
    ]

    def generate(self, base_claims: Optional[list[dict]] = None) -> list[dict]:
        base_claims = base_claims or self.SEED_CLAIMS
        adversarial = []
        for claim in base_claims:
            for template, attack_type in self.TEMPLATES:
                try:
                    text = template.format(**claim)
                    adversarial.append({
                        "claim": text,
                        "attack_type": attack_type,
                        "original": claim,
                        "expected_challenge": True,
                    })
                except KeyError:
                    continue
        return adversarial


class EvaluationService:
    def __init__(self, session: AsyncSession, settings: Optional[Settings] = None):
        self.session = session
        self.settings = settings or get_settings()
        self.skeptic = SkepticAgent(settings=self.settings)
        self.adversarial_generator = AdversarialTestGenerator()

    def _score_challenge_match(self, expected: list[str], predicted: list[str]) -> tuple[bool, bool]:
        """Return (hit, should_have_challenged) for one benchmark item."""
        expected_types = set(expected)
        predicted_types = set(predicted)
        should_challenge = bool(expected_types) or True  # benchmark items expect challenges
        if not expected_types:
            return bool(predicted_types), should_challenge
        return bool(expected_types & predicted_types), should_challenge

    async def get_latest_metrics(self, model_name: str = "base_skeptic") -> Optional[EvaluationMetrics]:
        result = await self.session.execute(
            select(EvaluationResult)
            .where(EvaluationResult.model_name == model_name)
            .order_by(EvaluationResult.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return EvaluationMetrics(
            challenge_recall=row.challenge_recall,
            challenge_precision=row.challenge_precision,
            challenge_f1=row.challenge_f1,
            miss_rate=row.miss_rate,
            avg_latency_ms=row.avg_latency_ms,
            avg_cost_usd=row.avg_cost_usd,
            model_name=row.model_name,
            sample_count=row.sample_count,
        )

    async def run_benchmark(
        self,
        benchmark_path: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> EvaluationMetrics:
        if model_name is None:
            from pathlib import Path as P

            if self.settings.use_finetuned_skeptic and P(self.settings.finetuned_skeptic_path).exists():
                model_name = "finetuned_skeptic"
            else:
                model_name = "base_skeptic"
        path = Path(benchmark_path or self.settings.benchmark_path)
        if not path.exists():
            logger.warning("benchmark_not_found", path=str(path))
            return EvaluationMetrics(
                challenge_recall=0.0, challenge_precision=0.0, challenge_f1=0.0,
                miss_rate=1.0, avg_latency_ms=0.0, avg_cost_usd=0.0,
                model_name=model_name, sample_count=0,
            )

        with open(path) as f:
            benchmark = json.load(f)

        debates = benchmark["debates"]
        max_n = self.settings.benchmark_max_samples
        if max_n > 0:
            debates = debates[:max_n]

        sem = asyncio.Semaphore(self.settings.eval_concurrency)

        async def eval_item(item: dict) -> dict:
            async with sem:
                from app.domain.models import AgentContext, Evidence

                evidence = [
                    Evidence(content=e, source_id="bench", source_title="benchmark", credibility=0.7)
                    for e in item.get("evidence", [])
                ]
                context = AgentContext(claim_text=item["claim"], evidence=evidence)
                response = await self.skeptic.challenge(context)
                expected = item.get("expected_challenges", [])
                predicted = [c.challenge_type.value for c in response.challenges]
                hit, should_challenge = self._score_challenge_match(expected, predicted)
                return {
                    "hit": hit,
                    "should_challenge": should_challenge,
                    "predicted": bool(predicted),
                    "latency_ms": response.latency_ms,
                    "cost_usd": response.cost_usd,
                }

        results = await asyncio.gather(*[eval_item(item) for item in debates])

        tp, fp, fn, tn = 0, 0, 0, 0
        latencies, costs = [], []
        for r in results:
            latencies.append(r["latency_ms"])
            costs.append(r["cost_usd"])
            if r["should_challenge"] and r["hit"]:
                tp += 1
            elif r["should_challenge"] and not r["hit"]:
                fn += 1
            elif not r["should_challenge"] and r["predicted"]:
                fp += 1
            else:
                tn += 1

        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        miss_rate = fn / (tp + fn) if (tp + fn) > 0 else 0.0

        metrics = EvaluationMetrics(
            challenge_recall=recall,
            challenge_precision=precision,
            challenge_f1=f1,
            miss_rate=miss_rate,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
            avg_cost_usd=sum(costs) / len(costs) if costs else 0.0,
            model_name=model_name,
            sample_count=len(debates),
        )

        api_model = (
            self.settings.finetuned_skeptic_model
            if self.settings.use_finetuned_skeptic
            else self.settings.base_skeptic_model
        )

        result = EvaluationResult(
            id=uuid.uuid4(),
            model_name=model_name,
            challenge_recall=metrics.challenge_recall,
            challenge_precision=metrics.challenge_precision,
            challenge_f1=metrics.challenge_f1,
            miss_rate=metrics.miss_rate,
            avg_latency_ms=metrics.avg_latency_ms,
            avg_cost_usd=metrics.avg_cost_usd,
            sample_count=metrics.sample_count,
            metrics_detail={"tp": tp, "fp": fp, "fn": fn, "tn": tn, "api_model": api_model},
        )
        self.session.add(result)
        await self.session.flush()

        if miss_rate > self.settings.adversarial_miss_rate_threshold:
            logger.warning("high_miss_rate_data_quality", miss_rate=miss_rate)

        return metrics

    async def run_adversarial_eval(self, model_name: str = "base_skeptic") -> dict:
        """Run adversarial claim generation and evaluate Skeptic detection rate."""
        claims = self.adversarial_generator.generate()
        max_n = self.settings.adversarial_max_claims
        if max_n > 0:
            claims = claims[:max_n]

        sem = asyncio.Semaphore(self.settings.eval_concurrency)
        attack_breakdown: dict[str, dict[str, int]] = {}
        detected = 0

        async def eval_claim(item: dict) -> tuple[str, bool]:
            async with sem:
                from app.domain.models import AgentContext, Evidence

                evidence = [
                    Evidence(
                        content=f"Reference: {item['original']}",
                        source_id="adversarial",
                        source_title="seed",
                        credibility=0.8,
                    )
                ]
                context = AgentContext(claim_text=item["claim"], evidence=evidence)
                response = await self.skeptic.challenge(context)
                return item["attack_type"], bool(response.challenges)

        outcomes = await asyncio.gather(*[eval_claim(item) for item in claims])
        for attack, was_detected in outcomes:
            if attack not in attack_breakdown:
                attack_breakdown[attack] = {"total": 0, "detected": 0}
            attack_breakdown[attack]["total"] += 1
            if was_detected:
                detected += 1
                attack_breakdown[attack]["detected"] += 1

        miss_rate = 1.0 - (detected / len(claims)) if claims else 0.0
        run = AdversarialEvalRun(
            id=uuid.uuid4(),
            total_claims=len(claims),
            challenges_detected=detected,
            miss_rate=miss_rate,
            attack_breakdown=attack_breakdown,
            model_name=model_name,
        )
        self.session.add(run)
        await self.session.flush()

        if miss_rate > self.settings.adversarial_miss_rate_threshold:
            logger.warning("adversarial_miss_rate_high", miss_rate=miss_rate)

        return {
            "run_id": str(run.id),
            "total_claims": len(claims),
            "challenges_detected": detected,
            "miss_rate": miss_rate,
            "attack_breakdown": attack_breakdown,
            "model_name": model_name,
        }

    async def get_adversarial_history(self, limit: int = 20) -> list[dict]:
        result = await self.session.execute(
            select(AdversarialEvalRun).order_by(AdversarialEvalRun.created_at.desc()).limit(limit)
        )
        runs = list(result.scalars().all())
        return [
            {
                "run_id": str(r.id),
                "total_claims": r.total_claims,
                "challenges_detected": r.challenges_detected,
                "miss_rate": r.miss_rate,
                "attack_breakdown": r.attack_breakdown,
                "model_name": r.model_name,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]

    async def compare_models(self) -> dict:
        result = await self.session.execute(
            select(EvaluationResult).order_by(EvaluationResult.created_at.desc()).limit(50)
        )
        rows = list(result.scalars().all())

        by_model: dict[str, EvaluationResult] = {}
        for row in rows:
            if row.model_name not in by_model:
                by_model[row.model_name] = row

        ordered_names = [n for n in ("base_skeptic", "finetuned_skeptic") if n in by_model]
        ordered_names.extend(n for n in by_model if n not in ordered_names)

        comparisons = [
            {
                "model": name,
                "challenge_recall": by_model[name].challenge_recall,
                "challenge_precision": by_model[name].challenge_precision,
                "challenge_f1": by_model[name].challenge_f1,
                "miss_rate": by_model[name].miss_rate,
                "avg_latency_ms": by_model[name].avg_latency_ms,
                "avg_cost_usd": by_model[name].avg_cost_usd,
                "sample_count": by_model[name].sample_count,
                "created_at": by_model[name].created_at.isoformat(),
                "inference_model": (by_model[name].metrics_detail or {}).get("api_model"),
            }
            for name in ordered_names
        ]

        return {
            "comparisons": comparisons,
            "has_base": "base_skeptic" in by_model,
            "has_finetuned": "finetuned_skeptic" in by_model,
        }

    async def generate_charts(self, output_dir: str = "data/evaluation/charts") -> str:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            return "matplotlib not installed"

        result = await self.session.execute(
            select(EvaluationResult).order_by(EvaluationResult.created_at.desc()).limit(20)
        )
        rows = list(result.scalars().all())
        if not rows:
            return "no evaluation data"

        # Latest result per model name (base vs fine-tuned)
        by_model: dict[str, EvaluationResult] = {}
        for row in rows:
            if row.model_name not in by_model:
                by_model[row.model_name] = row

        evals = []
        for name in ("base_skeptic", "finetuned_skeptic"):
            if name in by_model:
                evals.append(by_model[name])
        if not evals:
            evals = [rows[0]]

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        chart_path = Path(output_dir) / "skeptic_comparison.png"

        models = [e.model_name.replace("_", " ") for e in evals]
        f1_scores = [e.challenge_f1 for e in evals]
        miss_rates = [e.miss_rate for e in evals]
        colors_f1 = ["#3b82f6", "#10b981"][: len(evals)]
        colors_miss = ["#ef4444", "#f59e0b"][: len(evals)]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        x = range(len(evals))
        ax1.bar(x, f1_scores, color=colors_f1, width=0.6)
        ax1.set_title("Challenge F1 Score")
        ax1.set_ylim(0, 1)
        ax1.set_xticks(list(x))
        ax1.set_xticklabels(models, rotation=15, ha="right")

        ax2.bar(x, miss_rates, color=colors_miss, width=0.6)
        ax2.set_title("Miss Rate (lower is better)")
        ax2.set_ylim(0, max(0.3, max(miss_rates) * 1.2) if miss_rates else 0.3)
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(models, rotation=15, ha="right")

        fig.suptitle("Skeptic benchmark — held-out debates", fontsize=11, y=1.02)
        plt.tight_layout()
        plt.savefig(chart_path, bbox_inches="tight")
        plt.close()
        return str(chart_path)


class FineTuningPipeline:
    """QLoRA/LoRA fine-tuning pipeline with MLflow tracking."""

    def __init__(self, session: AsyncSession, settings: Optional[Settings] = None):
        self.session = session
        self.settings = settings or get_settings()
        self.training_builder = TrainingDatasetBuilder(session, self.settings)

    async def start_experiment(self, name: str) -> Experiment:
        blocked, reason = await self.training_builder.is_training_blocked()
        if blocked:
            raise ValueError(reason)

        experiment = Experiment(
            id=uuid.uuid4(),
            name=name,
            teacher_model=self.settings.teacher_model,
            student_model=self.settings.student_model,
            status="pending",
            config={"method": "qlora", "lora_r": 16, "lora_alpha": 32},
        )
        self.session.add(experiment)
        await self.session.flush()

        run_id = _mlflow_run_id(name, self.settings)
        experiment.mlflow_run_id = run_id
        experiment.status = "running"
        experiment.started_at = datetime.utcnow()
        if run_id:
            _mlflow_log_run(run_id, self.settings, params=experiment.config)

        await self.session.flush()
        return experiment

    async def run_finetuning(self, experiment_id: uuid.UUID, training_data_path: Optional[str] = None) -> dict:
        result = await self.session.execute(select(Experiment).where(Experiment.id == experiment_id))
        experiment = result.scalar_one_or_none()
        if not experiment:
            return {"status": "error", "message": "Experiment not found"}

        blocked, reason = await self.training_builder.is_training_blocked()
        if blocked:
            experiment.status = "blocked"
            await self.session.flush()
            return {"status": "blocked", "message": reason}

        data_path = training_data_path or str(
            Path(self.settings.training_data_dir) / "skeptic_train.jsonl"
        )
        await self.training_builder.export_jsonl(data_path)

        if not Path(data_path).exists() or Path(data_path).stat().st_size == 0:
            experiment.status = "failed"
            await self.session.flush()
            return {"status": "error", "message": "No training data available — verify more claims first"}

        try:
            logger.info("finetuning_started", experiment_id=str(experiment_id), data=data_path)
            train_result = run_qlora_finetuning(
                data_path,
                self.settings.finetuned_skeptic_path,
                self.settings,
            )

            if experiment.mlflow_run_id:
                if train_result.get("status") == "completed":
                    _mlflow_log_run(
                        experiment.mlflow_run_id,
                        self.settings,
                        metrics={"samples_trained": train_result.get("samples_trained", 0)},
                    )
                else:
                    _mlflow_log_run(
                        experiment.mlflow_run_id,
                        self.settings,
                        params={"error": train_result.get("message", "unknown")},
                    )

            if train_result.get("status") == "completed":
                experiment.status = "completed"
                experiment.completed_at = datetime.utcnow()
            else:
                experiment.status = "failed"

            await self.session.flush()
            return {
                **train_result,
                "experiment_id": str(experiment_id),
            }
        except Exception as e:
            experiment.status = "failed"
            await self.session.flush()
            return {"status": "failed", "error": str(e)}

    async def get_status(self) -> dict:
        result = await self.session.execute(
            select(Experiment).order_by(Experiment.created_at.desc()).limit(5)
        )
        experiments = list(result.scalars().all())
        blocked, block_reason = await self.training_builder.is_training_blocked()
        return {
            "training_blocked": blocked,
            "training_block_reason": block_reason if blocked else None,
            "finetuned_path": self.settings.finetuned_skeptic_path,
            "use_finetuned_skeptic": self.settings.use_finetuned_skeptic,
            "experiments": [
                {
                    "id": str(e.id),
                    "name": e.name,
                    "status": e.status,
                    "teacher_model": e.teacher_model,
                    "student_model": e.student_model,
                    "started_at": e.started_at.isoformat() if e.started_at else None,
                    "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                }
                for e in experiments
            ],
        }
