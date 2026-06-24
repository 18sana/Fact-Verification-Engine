from datetime import datetime
from typing import Optional
from uuid import UUID

from app.agents.llm_client import LLMClient, parse_json_response
from app.agents.prompts import ADVOCATE_SYSTEM_PROMPT, CLAIM_EXTRACTION_PROMPT, JUDGE_SYSTEM_PROMPT
from app.agents.refs import normalize_evidence_refs
from app.core.config import Settings, get_settings
from app.core.exceptions import AgentError, ClaimExtractionError
from app.core.logging import get_logger
from app.domain.enums import AgentRole, Verdict
from app.domain.models import AgentContext, AgentResponse, AtomicClaim, Evidence

logger = get_logger(__name__)


class ClaimExtractionAgent:
    def __init__(self, llm: Optional[LLMClient] = None, settings: Optional[Settings] = None):
        self.llm = llm or LLMClient(settings)
        self.settings = settings or get_settings()

    async def extract(self, claim_text: str, parent_claim_id: Optional[UUID] = None) -> list[AtomicClaim]:
        user_prompt = f"Extract atomic claims from:\n\n{claim_text}"
        try:
            raw, latency, cost = await self.llm.complete(CLAIM_EXTRACTION_PROMPT, user_prompt, agent="extractor")
            data = parse_json_response(raw)
            claims = []
            for item in data.get("claims", []):
                ts = None
                if item.get("timestamp"):
                    try:
                        ts = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass
                claims.append(
                    AtomicClaim(
                        subject=item["subject"],
                        predicate=item["predicate"],
                        object=item["object"],
                        timestamp=ts,
                        parent_claim_id=parent_claim_id,
                        weight=float(item.get("weight", 1.0)),
                    )
                )
            if not claims:
                claims.append(AtomicClaim(subject=claim_text, predicate="states", object=claim_text, parent_claim_id=parent_claim_id))
            return claims
        except Exception as e:
            raise ClaimExtractionError(f"Failed to extract claims: {e}") from e


class AdvocateAgent:
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()

    async def defend(self, context: AgentContext) -> AgentResponse:
        evidence_text = self._format_evidence(context.evidence)
        user_prompt = f"""Claim: {context.claim_text}

Retrieved Evidence:
{evidence_text}

Defend this claim using only the evidence above."""

        try:
            raw, latency, cost = await self.llm.complete(ADVOCATE_SYSTEM_PROMPT, user_prompt, agent="advocate")
            data = parse_json_response(raw)
            return AgentResponse(
                agent=AgentRole.ADVOCATE,
                reasoning=data.get("reasoning", ""),
                confidence=float(data.get("confidence", 0.5)),
                sources=normalize_evidence_refs(data.get("sources", []), context.evidence),
                evidence_used=normalize_evidence_refs(data.get("evidence_used", []), context.evidence),
                latency_ms=latency,
                cost_usd=cost,
                prompt=user_prompt,
                raw_response=raw,
            )
        except Exception as e:
            raise AgentError(str(e), "advocate") from e

    @staticmethod
    def _format_evidence(evidence: list[Evidence]) -> str:
        if not evidence:
            return "No evidence available."
        lines = []
        for i, ev in enumerate(evidence, 1):
            lines.append(
                f"[{i}] {ev.source_title} (credibility={ev.credibility:.0%}): {ev.content}"
            )
        return "\n".join(lines)


class SkepticAgent:
    def __init__(self, settings: Optional[Settings] = None):
        from app.agents.skeptic_router import SkepticRouter

        self.settings = settings or get_settings()
        self.router = SkepticRouter(self.settings)

    async def challenge(self, context: AgentContext) -> AgentResponse:
        evidence_text = AdvocateAgent._format_evidence(context.evidence)
        advocate_text = context.advocate_response.reasoning if context.advocate_response else "No advocate response."

        user_prompt = f"""Claim: {context.claim_text}

Retrieved Evidence:
{evidence_text}

Advocate's Defense:
{advocate_text}

Challenge this claim adversarially using only the evidence above."""

        try:
            return await self.router.challenge(context, user_prompt)
        except Exception as e:
            raise AgentError(str(e), "skeptic") from e


class JudgeAgent:
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()

    async def evaluate(self, context: AgentContext) -> AgentResponse:
        evidence_text = AdvocateAgent._format_evidence(context.evidence)
        advocate = context.advocate_response
        skeptic = context.skeptic_response

        user_prompt = f"""Original Claim: {context.claim_text}

Evidence:
{evidence_text}

Advocate:
{advocate.reasoning if advocate else 'N/A'}
Confidence: {advocate.confidence if advocate else 'N/A'}

Skeptic:
{skeptic.reasoning if skeptic else 'N/A'}
Confidence: {skeptic.confidence if skeptic else 'N/A'}
Challenges: {json_challenges(skeptic) if skeptic else 'N/A'}

Render your verdict."""

        try:
            raw, latency, cost = await self.llm.complete(JUDGE_SYSTEM_PROMPT, user_prompt, agent="judge")
            data = parse_json_response(raw)
            try:
                verdict = Verdict(data.get("verdict", "insufficient_evidence"))
            except ValueError:
                verdict = Verdict.INSUFFICIENT_EVIDENCE

            return AgentResponse(
                agent=AgentRole.JUDGE,
                reasoning=data.get("reasoning", ""),
                confidence=float(data.get("confidence", 0.5)),
                evidence_used=normalize_evidence_refs(data.get("evidence_used", []), context.evidence),
                verdict=verdict,
                latency_ms=latency,
                cost_usd=cost,
                prompt=user_prompt,
                raw_response=raw,
            )
        except Exception as e:
            raise AgentError(str(e), "judge") from e


def json_challenges(skeptic: AgentResponse) -> str:
    return str([{"type": c.challenge_type.value, "desc": c.description} for c in skeptic.challenges])
