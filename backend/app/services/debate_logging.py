import uuid
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.models import Debate, DebateTurn, HumanReview
from app.domain.enums import HumanReviewStatus
from app.domain.models import AgentResponse, Evidence

logger = get_logger(__name__)


class DebateLoggingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_debate(self, claim_id: UUID) -> Debate:
        debate = Debate(id=uuid.uuid4(), claim_id=claim_id)
        self.session.add(debate)
        await self.session.flush()
        return debate

    async def log_turn(
        self,
        debate_id: UUID,
        agent: str,
        claim_text: str,
        prompt: str,
        response: AgentResponse,
        evidence: list[Evidence],
    ) -> DebateTurn:
        turn = DebateTurn(
            id=uuid.uuid4(),
            debate_id=debate_id,
            agent=agent,
            claim_text=claim_text,
            prompt=prompt,
            response=response.raw_response or response.reasoning,
            retrieved_evidence=[{"id": str(e.id), "content": e.content[:200]} for e in evidence],
            confidence=response.confidence,
            source_ids=response.sources,
            latency_ms=response.latency_ms,
            cost_usd=response.cost_usd,
        )
        self.session.add(turn)
        await self.session.flush()
        return turn

    async def finalize_debate(
        self,
        debate: Debate,
        verdict: str,
        confidence: float,
        requires_human_review: bool,
        total_latency: float,
        total_cost: float,
    ) -> Debate:
        debate.verdict = verdict
        debate.confidence = confidence
        debate.requires_human_review = requires_human_review
        debate.total_latency_ms = total_latency
        debate.total_cost_usd = total_cost
        await self.session.flush()
        return debate

    async def get_debate(self, debate_id: UUID) -> Optional[Debate]:
        result = await self.session.execute(
            select(Debate).where(Debate.id == debate_id)
        )
        return result.scalar_one_or_none()

    async def list_debates(self, skip: int = 0, limit: int = 20) -> list[Debate]:
        result = await self.session.execute(
            select(Debate).order_by(Debate.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_debate_count(self) -> int:
        result = await self.session.execute(select(func.count(Debate.id)))
        return result.scalar() or 0


class HumanEscalationService:
    def __init__(self, session: AsyncSession, settings: Optional[Settings] = None):
        self.session = session
        self.settings = settings or get_settings()

    def should_escalate(self, judge_confidence: float) -> bool:
        return judge_confidence < self.settings.human_review_threshold

    async def create_review(self, debate_id: UUID, claim_text: str, judge_confidence: float) -> HumanReview:
        review = HumanReview(
            id=uuid.uuid4(),
            debate_id=debate_id,
            claim_text=claim_text,
            judge_confidence=judge_confidence,
            status=HumanReviewStatus.PENDING.value,
        )
        self.session.add(review)
        await self.session.flush()
        logger.info("human_review_created", debate_id=str(debate_id), confidence=judge_confidence)
        return review

    async def list_pending(self, skip: int = 0, limit: int = 20) -> list[HumanReview]:
        result = await self.session.execute(
            select(HumanReview)
            .where(HumanReview.status == HumanReviewStatus.PENDING.value)
            .order_by(HumanReview.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
