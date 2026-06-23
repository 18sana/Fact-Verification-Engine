import time
from pathlib import Path
from typing import Optional

from app.agents.llm_client import LLMClient, parse_json_response
from app.agents.refs import normalize_evidence_refs
from app.agents.prompts import SKEPTIC_SYSTEM_PROMPT
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.enums import AgentRole, ChallengeType
from app.domain.models import AgentContext, AgentResponse, Challenge

logger = get_logger(__name__)


class LocalSkepticModel:
    """Loads fine-tuned student model (Phi-2 + optional LoRA adapter) for inference."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._model = None
        self._tokenizer = None
        self._loaded_path: Optional[str] = None

    def is_available(self) -> bool:
        if not self.settings.use_local_skeptic:
            return False
        path = Path(self.settings.finetuned_skeptic_path)
        return self.settings.use_finetuned_skeptic and path.exists()

    def _load(self) -> None:
        path = Path(self.settings.finetuned_skeptic_path)
        if self._model is not None and self._loaded_path == str(path):
            return

        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("loading_local_skeptic", path=str(path), base=self.settings.student_model)

        self._tokenizer = AutoTokenizer.from_pretrained(self.settings.student_model)
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        adapter_config = path / "adapter_config.json"
        if adapter_config.exists():
            from peft import PeftModel

            base = AutoModelForCausalLM.from_pretrained(
                self.settings.student_model,
                device_map="auto" if self._has_cuda() else None,
                torch_dtype="auto",
            )
            self._model = PeftModel.from_pretrained(base, str(path))
        else:
            self._model = AutoModelForCausalLM.from_pretrained(
                str(path) if (path / "config.json").exists() else self.settings.student_model,
                device_map="auto" if self._has_cuda() else None,
                torch_dtype="auto",
            )

        self._model.eval()
        self._loaded_path = str(path)

    @staticmethod
    def _has_cuda() -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def generate(self, user_prompt: str) -> str:
        import torch

        self._load()
        messages = f"{SKEPTIC_SYSTEM_PROMPT}\n\n{user_prompt}\n\nRespond in JSON only."
        inputs = self._tokenizer(messages, return_tensors="pt", truncation=True, max_length=2048)
        if self._has_cuda():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.1,
                do_sample=True,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        return self._tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


class SkepticRouter:
    """Routes Skeptic inference to fine-tuned local model or teacher API."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.api_llm = LLMClient(self.settings)
        self.local_model = LocalSkepticModel(self.settings)

    @property
    def active_backend(self) -> str:
        return "finetuned_local" if self.local_model.is_available() else "api"

    def _api_model(self) -> str:
        if self.settings.use_finetuned_skeptic:
            return self.settings.finetuned_skeptic_model
        return self.settings.base_skeptic_model

    async def challenge(self, context: AgentContext, user_prompt: str) -> AgentResponse:
        start = time.perf_counter()

        if self.local_model.is_available():
            try:
                raw = self.local_model.generate(user_prompt)
                latency = (time.perf_counter() - start) * 1000
                logger.info("skeptic_using_finetuned", latency_ms=latency)
                return self._parse_response(
                    raw, user_prompt, latency, cost_usd=0.0, backend="finetuned_local", evidence=context.evidence
                )
            except Exception as e:
                logger.warning("finetuned_skeptic_failed_fallback", error=str(e))

        api_model = self._api_model()
        raw, latency, cost = await self.api_llm.complete(
            SKEPTIC_SYSTEM_PROMPT, user_prompt, agent="skeptic", model=api_model
        )
        logger.info("skeptic_using_api", model=api_model)
        try:
            return self._parse_response(
                raw, user_prompt, latency, cost, backend="api", evidence=context.evidence, api_model=api_model
            )
        except Exception as e:
            logger.warning("skeptic_json_parse_failed_retry", model=api_model, error=str(e))
            raw, latency, cost = await self.api_llm.complete(
                SKEPTIC_SYSTEM_PROMPT,
                f"{user_prompt}\n\nReturn valid JSON only. No markdown.",
                agent="skeptic",
                model=api_model,
            )
            return self._parse_response(
                raw, user_prompt, latency, cost, backend="api", evidence=context.evidence, api_model=api_model
            )

    def _parse_response(
        self,
        raw: str,
        user_prompt: str,
        latency: float,
        cost_usd: float,
        backend: str,
        evidence=None,
        api_model: Optional[str] = None,
    ) -> AgentResponse:
        data = parse_json_response(raw)
        challenges = []
        for ch in data.get("challenges", []):
            try:
                challenge_type = ChallengeType(ch["challenge_type"])
            except (ValueError, KeyError):
                challenge_type = ChallengeType.WEAK_EVIDENCE
            challenges.append(
                Challenge(
                    challenge_type=challenge_type,
                    description=ch.get("description", ""),
                    reasoning=ch.get("reasoning", ""),
                    evidence_refs=normalize_evidence_refs(ch.get("evidence_refs", []), evidence),
                    confidence=float(ch.get("confidence", 0.5)),
                )
            )
        return AgentResponse(
            agent=AgentRole.SKEPTIC,
            reasoning=data.get("reasoning", ""),
            confidence=float(data.get("confidence", 0.5)),
            sources=normalize_evidence_refs(data.get("sources", []), evidence),
            challenges=challenges,
            latency_ms=latency,
            cost_usd=cost_usd,
            prompt=user_prompt,
            raw_response=raw,
            metadata={"backend": backend, "api_model": api_model},
        )
