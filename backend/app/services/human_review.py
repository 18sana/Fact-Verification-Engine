import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.llm_client import parse_json_response
from app.core.logging import get_logger
from app.db.models import Debate, HumanReview
from app.domain.enums import AgentRole, ChallengeType, HumanReviewStatus, Verdict
from app.domain.models import AgentResponse, AtomicClaim, Challenge, DebateResult, Evidence
from app.services.training import TrainingDatasetBuilder

logger = get_logger(__name__)


class HumanReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.training_builder = TrainingDatasetBuilder(session)

    async def sync_missing_reviews(self) -> int:
        """Create pending reviews for flagged debates that never got a queue entry."""
        reviewed_debate_ids = select(HumanReview.debate_id)
        result = await self.session.execute(
            select(Debate)
            .options(selectinload(Debate.claim))
            .where(Debate.requires_human_review.is_(True))
            .where(Debate.id.not_in(reviewed_debate_ids))
        )
        created = 0
        for debate in result.scalars().all():
            claim_text = debate.claim.text if debate.claim else "Unknown claim"
            review = HumanReview(
                debate_id=debate.id,
                claim_text=claim_text,
                judge_confidence=debate.confidence or 0.0,
                status=HumanReviewStatus.PENDING.value,
            )
            self.session.add(review)
            created += 1
        if created:
            await self.session.flush()
            logger.info("human_reviews_synced", created=created)
        return created

    async def list_pending(self, skip: int = 0, limit: int = 20) -> list[HumanReview]:
        result = await self.session.execute(
            select(HumanReview)
            .where(HumanReview.status == HumanReviewStatus.PENDING.value)
            .order_by(HumanReview.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_pending(self) -> int:
        result = await self.session.execute(
            select(func.count(HumanReview.id)).where(HumanReview.status == HumanReviewStatus.PENDING.value)
        )
        return result.scalar() or 0

    async def get_review(self, review_id: UUID) -> Optional[HumanReview]:
        result = await self.session.execute(select(HumanReview).where(HumanReview.id == review_id))
        return result.scalar_one_or_none()

    async def approve(self, review_id: UUID, notes: Optional[str] = None) -> HumanReview:
        review = await self.get_review(review_id)
        if not review:
            raise ValueError("Review not found")
        if review.status != HumanReviewStatus.PENDING.value:
            raise ValueError("Review already resolved")

        review.status = HumanReviewStatus.APPROVED.value
        review.reviewer_notes = notes
        review.resolved_at = datetime.utcnow()

        debate = await self._load_debate(review.debate_id)
        if debate:
            debate.requires_human_review = False
            result = self._reconstruct_debate_result(debate, review.claim_text)
            await self.training_builder.maybe_create_sample(
                debate.id, result, requires_human_review=True, human_approved=True
            )

        await self.session.flush()
        logger.info("human_review_approved", review_id=str(review_id))
        return review

    async def reject(self, review_id: UUID, notes: Optional[str] = None) -> HumanReview:
        review = await self.get_review(review_id)
        if not review:
            raise ValueError("Review not found")
        if review.status != HumanReviewStatus.PENDING.value:
            raise ValueError("Review already resolved")

        review.status = HumanReviewStatus.REJECTED.value
        review.reviewer_notes = notes
        review.resolved_at = datetime.utcnow()

        debate = await self._load_debate(review.debate_id)
        if debate:
            debate.requires_human_review = False

        await self.session.flush()
        logger.info("human_review_rejected", review_id=str(review_id))
        return review

    async def _load_debate(self, debate_id: UUID) -> Optional[Debate]:
        result = await self.session.execute(
            select(Debate).where(Debate.id == debate_id).options(selectinload(Debate.turns))
        )
        return result.scalar_one_or_none()

    def _parse_agent_response(self, agent_name: str, turn) -> AgentResponse:
        role = AgentRole(agent_name)
        try:
            data = parse_json_response(turn.response)
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
                        evidence_refs=ch.get("evidence_refs", []),
                        confidence=float(ch.get("confidence", 0.5)),
                    )
                )
            verdict = None
            if data.get("verdict"):
                try:
                    verdict = Verdict(data["verdict"])
                except ValueError:
                    pass
            return AgentResponse(
                agent=role,
                reasoning=data.get("reasoning", turn.response[:500]),
                confidence=float(data.get("confidence", turn.confidence or 0.0)),
                sources=data.get("sources", []),
                challenges=challenges,
                verdict=verdict,
                latency_ms=turn.latency_ms,
                cost_usd=turn.cost_usd,
                raw_response=turn.response,
            )
        except Exception:
            return AgentResponse(
                agent=role,
                reasoning=turn.response[:500],
                confidence=turn.confidence or 0.0,
                raw_response=turn.response,
            )

    def _reconstruct_evidence(self, debate: Debate) -> list[Evidence]:
        evidence: list[Evidence] = []
        for turn in debate.turns:
            raw_evidence = turn.retrieved_evidence or []
            if isinstance(raw_evidence, list):
                for item in raw_evidence:
                    if isinstance(item, dict):
                        evidence.append(
                            Evidence(
                                content=item.get("content", ""),
                                source_id=item.get("source_id", "unknown"),
                                source_title=item.get("source_title", "unknown"),
                                source_url=item.get("source_url"),
                                credibility=float(item.get("credibility", 0.5)),
                            )
                        )
            if evidence:
                break
        return evidence

    def _reconstruct_debate_result(self, debate: Debate, claim_text: str) -> DebateResult:
        turns = {t.agent: t for t in debate.turns}
        empty = AgentResponse(agent=AgentRole.JUDGE, reasoning="", confidence=0.0)

        advocate = self._parse_agent_response("advocate", turns["advocate"]) if "advocate" in turns else empty
        skeptic = self._parse_agent_response("skeptic", turns["skeptic"]) if "skeptic" in turns else empty
        judge = self._parse_agent_response("judge", turns["judge"]) if "judge" in turns else empty

        try:
            verdict = Verdict(debate.verdict or "insufficient_evidence")
        except ValueError:
            verdict = Verdict.INSUFFICIENT_EVIDENCE

        return DebateResult(
            claim_id=debate.claim_id,
            debate_id=debate.id,
            atomic_claims=[AtomicClaim(subject=claim_text, predicate="states", object=claim_text)],
            advocate=advocate,
            skeptic=skeptic,
            judge=judge,
            overall_verdict=verdict,
            overall_confidence=debate.confidence or 0.0,
            requires_human_review=True,
            evidence=self._reconstruct_evidence(debate),
        )
