import json
import uuid
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.teacher_labeler import TeacherLabeler
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.models import EvaluationResult, TrainingSample
from app.domain.models import DebateResult
from app.retrieval.hybrid import EmbeddingService

logger = get_logger(__name__)


class DuplicateDetector:
    def __init__(self, embedding_service: EmbeddingService, settings: Optional[Settings] = None):
        self.embedding_service = embedding_service
        self.settings = settings or get_settings()

    async def is_duplicate(self, session: AsyncSession, embedding: list[float]) -> bool:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        threshold = self.settings.duplicate_similarity_threshold

        sql = text("""
            SELECT 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM training_samples
            WHERE embedding IS NOT NULL AND is_duplicate = false
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT 1
        """)
        result = await session.execute(sql, {"embedding": embedding_str})
        row = result.fetchone()
        if row and row.similarity >= threshold:
            logger.info("duplicate_detected", similarity=row.similarity)
            return True
        return False


class TrainingDatasetBuilder:
    def __init__(self, session: AsyncSession, settings: Optional[Settings] = None):
        self.session = session
        self.settings = settings or get_settings()
        self.embedding_service = EmbeddingService(self.settings)
        self.duplicate_detector = DuplicateDetector(self.embedding_service, self.settings)
        self.teacher = TeacherLabeler(self.settings)

    async def is_training_blocked(self) -> tuple[bool, str]:
        """Block training when recent benchmark miss rate exceeds threshold (data quality issue)."""
        result = await self.session.execute(
            select(EvaluationResult)
            .where(EvaluationResult.model_name == "base_skeptic")
            .order_by(EvaluationResult.created_at.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        if latest and latest.miss_rate > self.settings.training_block_miss_rate_threshold:
            return True, (
                f"Benchmark miss rate {latest.miss_rate:.1%} exceeds training threshold "
                f"{self.settings.training_block_miss_rate_threshold:.1%} — re-run Evaluation or improve Skeptic first"
            )
        return False, ""

    def is_eligible(
        self,
        debate_result: DebateResult,
        requires_human_review: bool,
        human_approved: bool = False,
    ) -> bool:
        if requires_human_review and not human_approved:
            return False
        if debate_result.judge.confidence < self.settings.training_confidence_threshold:
            return False
        if not debate_result.evidence:
            return False
        has_challenge = bool(debate_result.skeptic.challenges) or bool(debate_result.skeptic.reasoning)
        if not has_challenge:
            return False
        return True

    async def maybe_create_sample(
        self,
        debate_id: UUID,
        debate_result: DebateResult,
        requires_human_review: bool,
        human_approved: bool = False,
    ) -> Optional[TrainingSample]:
        blocked, reason = await self.is_training_blocked()
        if blocked:
            logger.warning("training_blocked_by_miss_rate", reason=reason)
            return None

        if not self.is_eligible(debate_result, requires_human_review, human_approved):
            logger.info("training_sample_ineligible", debate_id=str(debate_id))
            return None

        claim_text = debate_result.atomic_claims[0].subject if debate_result.atomic_claims else ""
        if len(debate_result.atomic_claims) > 1:
            claim_text = " | ".join(f"{ac.subject} {ac.predicate} {ac.object}" for ac in debate_result.atomic_claims)

        challenge_text, teacher_reasoning = await self.teacher.label_challenge(
            claim_text,
            debate_result.evidence,
            debate_result.skeptic,
        )

        combined_text = f"{claim_text} {challenge_text}"
        embedding = (await self.embedding_service.embed([combined_text]))[0].tolist()

        if await self.duplicate_detector.is_duplicate(self.session, embedding):
            sample = TrainingSample(
                id=uuid.uuid4(),
                debate_id=debate_id,
                instruction="Challenge the following factual claim adversarially.",
                claim=claim_text,
                evidence=[e.content for e in debate_result.evidence],
                correct_challenge=challenge_text,
                judge_reasoning=teacher_reasoning or debate_result.judge.reasoning,
                embedding=embedding,
                is_duplicate=True,
                human_approved=human_approved,
            )
            self.session.add(sample)
            await self.session.flush()
            return None

        sample = TrainingSample(
            id=uuid.uuid4(),
            debate_id=debate_id,
            instruction="Challenge the following factual claim adversarially.",
            claim=claim_text,
            evidence=[e.content for e in debate_result.evidence],
            correct_challenge=challenge_text,
            judge_reasoning=teacher_reasoning or debate_result.judge.reasoning,
            embedding=embedding,
            is_duplicate=False,
            human_approved=human_approved or not requires_human_review,
        )
        self.session.add(sample)
        await self.session.flush()
        logger.info("training_sample_created", sample_id=str(sample.id))
        return sample

    async def get_stats(self) -> dict:
        total = await self.session.execute(select(TrainingSample))
        samples = list(total.scalars().all())
        blocked, block_reason = await self.is_training_blocked()
        return {
            "total_samples": len(samples),
            "eligible_samples": len([s for s in samples if not s.is_duplicate]),
            "duplicates_rejected": len([s for s in samples if s.is_duplicate]),
            "human_approved": len([s for s in samples if s.human_approved]),
            "training_blocked": blocked,
            "training_block_reason": block_reason if blocked else None,
        }

    async def export_jsonl(self, output_path: Optional[str] = None) -> list[dict]:
        result = await self.session.execute(
            select(TrainingSample).where(
                TrainingSample.is_duplicate == False,  # noqa: E712
                TrainingSample.human_approved == True,  # noqa: E712
            )
        )
        samples = result.scalars().all()
        records = [
            {
                "instruction": s.instruction,
                "input": f"Claim: {s.claim}\nEvidence: {'; '.join(s.evidence)}",
                "output": s.correct_challenge,
            }
            for s in samples
        ]
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                for rec in records:
                    f.write(json.dumps(rec) + "\n")
            logger.info("training_data_exported", path=str(path), count=len(records))
        return records
