import json
from typing import Optional

from app.agents.llm_client import LLMClient, parse_json_response
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.models import AgentResponse, Evidence

logger = get_logger(__name__)

TEACHER_LABEL_PROMPT = """You are the teacher model for Skeptic fine-tuning.

Given a factual claim, retrieved evidence, and the Skeptic's draft challenges, produce the OPTIMAL adversarial challenge that:
1. Is grounded only in the provided evidence
2. Is specific and adversarial (not generic criticism)
3. Would best expose flaws in the claim

Output JSON:
{
  "correct_challenge": "string - the ideal challenge text",
  "challenge_type": "one of the standard challenge types",
  "reasoning": "why this is the best challenge"
}
"""


class TeacherLabeler:
    """Uses the teacher model (larger LLM) to label optimal Skeptic challenges."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._teacher_llm: Optional[LLMClient] = None

    def _get_teacher_llm(self) -> LLMClient:
        if self._teacher_llm is None:
            teacher_settings = self.settings.model_copy()
            teacher_settings.llm_model = self.settings.teacher_model
            self._teacher_llm = LLMClient(teacher_settings)
        return self._teacher_llm

    async def label_challenge(
        self,
        claim: str,
        evidence: list[Evidence],
        skeptic_response: AgentResponse,
    ) -> tuple[str, str]:
        evidence_text = "\n".join(
            f"- [{ev.source_title}] (cred={ev.credibility}): {ev.content}" for ev in evidence
        )
        challenges_text = json.dumps(
            [{"type": c.challenge_type.value, "desc": c.description} for c in skeptic_response.challenges]
        )

        user_prompt = f"""Claim: {claim}

Evidence:
{evidence_text}

Skeptic draft challenges:
{challenges_text}

Skeptic reasoning:
{skeptic_response.reasoning}

Produce the optimal training label for the Skeptic."""

        try:
            llm = self._get_teacher_llm()
            raw, _, _ = await llm.complete(TEACHER_LABEL_PROMPT, user_prompt, agent="teacher")
            data = parse_json_response(raw)
            challenge = data.get("correct_challenge", "")
            reasoning = data.get("reasoning", "")
            if challenge:
                return challenge, reasoning
        except Exception as e:
            logger.warning("teacher_labeling_failed", error=str(e))

        if skeptic_response.challenges:
            return skeptic_response.challenges[0].description, skeptic_response.reasoning
        return skeptic_response.reasoning, skeptic_response.reasoning
