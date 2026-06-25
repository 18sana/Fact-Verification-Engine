import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AdvocateAgent, ClaimExtractionAgent, JudgeAgent, SkepticAgent
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.models import AtomicClaimDB, Claim
from app.domain.enums import Verdict, VerificationStatus
from app.domain.models import AgentContext, AtomicClaim, DebateResult, Evidence, SourceRef
from app.knowledge_graph import TemporalKnowledgeGraph
from app.retrieval.hybrid import HybridRetrievalService
from app.services.confidence import ConfidenceService
from app.services.debate_logging import DebateLoggingService, HumanEscalationService
from app.services.training import TrainingDatasetBuilder

logger = get_logger(__name__)


class VerificationService:
    """Main application service orchestrating claim verification."""

    def __init__(
        self,
        session: AsyncSession,
        kg: Optional[TemporalKnowledgeGraph] = None,
        settings: Optional[Settings] = None,
    ):
        self.session = session
        self.settings = settings or get_settings()
        self.kg = kg or TemporalKnowledgeGraph(self.settings)
        self.claim_extractor = ClaimExtractionAgent(settings=self.settings)
        self.advocate = AdvocateAgent()
        self.skeptic = SkepticAgent(settings=self.settings)
        self.judge = JudgeAgent()
        self.retrieval = HybridRetrievalService(session, self.settings)
        self.confidence_service = ConfidenceService()
        self.debate_logger = DebateLoggingService(session)
        self.escalation = HumanEscalationService(session, self.settings)
        self.training_builder = TrainingDatasetBuilder(session, self.settings)

    async def verify_claim(self, claim_text: str, user_id: Optional[UUID] = None) -> DebateResult:
        logger.info("verification_started", claim=claim_text[:100])

        claim = Claim(id=uuid.uuid4(), text=claim_text, user_id=user_id)
        self.session.add(claim)
        await self.session.flush()

        atomic_claims = await self.claim_extractor.extract(claim_text, parent_claim_id=claim.id)
        for ac in atomic_claims:
            ac.parent_claim_id = claim.id

        await self._persist_atomic_claims(claim.id, atomic_claims)

        query = self._build_retrieval_query(claim_text, atomic_claims)
        evidence = await self.retrieval.retrieve(query)

        if not evidence:
            return await self._handle_insufficient_evidence(claim, atomic_claims)

        debate = await self.debate_logger.create_debate(claim.id)
        context = AgentContext(claim_text=claim_text, evidence=evidence)

        advocate_response = await self.advocate.defend(context)
        await self.debate_logger.log_turn(debate.id, "advocate", claim_text, advocate_response.prompt, advocate_response, evidence)
        context.advocate_response = advocate_response

        skeptic_response = await self.skeptic.challenge(context)
        await self.debate_logger.log_turn(debate.id, "skeptic", claim_text, skeptic_response.prompt, skeptic_response, evidence)
        context.skeptic_response = skeptic_response

        judge_response = await self.judge.evaluate(context)
        await self.debate_logger.log_turn(debate.id, "judge", claim_text, judge_response.prompt, judge_response, evidence)

        judge_confidence = judge_response.confidence
        atomic_claims = self.confidence_service.propagate_to_atomic_claims(
            atomic_claims, evidence, judge_confidence
        )
        atomic_claims = self._enrich_with_evidence_sources(atomic_claims, evidence)
        overall_confidence = self.confidence_service.overall_from_atomic_and_judge(
            atomic_claims, judge_confidence
        )
        overall_verdict = judge_response.verdict or Verdict.INSUFFICIENT_EVIDENCE

        await self._update_atomic_confidences_in_db(atomic_claims)
        await self._update_knowledge_graph(atomic_claims)

        requires_review = self.escalation.should_escalate(overall_confidence)
        if requires_review:
            await self.escalation.create_review(debate.id, claim_text, overall_confidence)

        total_latency = advocate_response.latency_ms + skeptic_response.latency_ms + judge_response.latency_ms
        total_cost = advocate_response.cost_usd + skeptic_response.cost_usd + judge_response.cost_usd

        await self.debate_logger.finalize_debate(
            debate, overall_verdict.value, overall_confidence, requires_review, total_latency, total_cost
        )

        claim.overall_verdict = overall_verdict.value
        claim.overall_confidence = overall_confidence
        await self.session.flush()

        result = DebateResult(
            claim_id=claim.id,
            debate_id=debate.id,
            atomic_claims=atomic_claims,
            advocate=advocate_response,
            skeptic=skeptic_response,
            judge=judge_response,
            overall_verdict=overall_verdict,
            overall_confidence=overall_confidence,
            requires_human_review=requires_review,
            evidence=evidence,
        )

        if not requires_review:
            await self.training_builder.maybe_create_sample(debate.id, result, requires_review)

        logger.info(
            "verification_complete",
            verdict=overall_verdict.value,
            confidence=overall_confidence,
            skeptic_backend=skeptic_response.metadata.get("backend", "api"),
        )
        return result

    @staticmethod
    def _enrich_with_evidence_sources(
        claims: list[AtomicClaim], evidence: list[Evidence]
    ) -> list[AtomicClaim]:
        """Attach top evidence sources with credibility to atomic claims for KG edges."""
        top_sources = [
            SourceRef(
                source_id=ev.source_id,
                title=ev.source_title,
                url=ev.source_url,
                credibility=ev.credibility,
            )
            for ev in evidence[:3]
        ]
        for claim in claims:
            claim.source_refs = top_sources
        return claims

    async def _persist_atomic_claims(self, claim_id: UUID, claims: list[AtomicClaim]) -> None:
        for ac in claims:
            db_claim = AtomicClaimDB(
                id=ac.id,
                parent_claim_id=claim_id,
                subject=ac.subject,
                predicate=ac.predicate,
                object=ac.object,
                claim_timestamp=ac.timestamp,
                source_refs=[ref.model_dump() for ref in ac.source_refs],
                confidence=ac.confidence,
                weight=ac.weight,
                verification_status=ac.verification_status.value,
            )
            self.session.add(db_claim)
        await self.session.flush()

    async def _update_atomic_confidences_in_db(self, claims: list[AtomicClaim]) -> None:
        for ac in claims:
            result = await self.session.execute(select(AtomicClaimDB).where(AtomicClaimDB.id == ac.id))
            db_claim = result.scalar_one_or_none()
            if db_claim:
                db_claim.confidence = ac.confidence
                db_claim.source_refs = [ref.model_dump() for ref in ac.source_refs]
                if ac.confidence >= 0.85:
                    db_claim.verification_status = VerificationStatus.SUPPORTED.value
                elif ac.confidence < 0.4:
                    db_claim.verification_status = VerificationStatus.REFUTED.value
        await self.session.flush()

    async def _update_knowledge_graph(self, claims: list[AtomicClaim]) -> None:
        try:
            await self.kg.connect()
            for claim in claims:
                await self.kg.upsert_claim(claim)
        except Exception as e:
            logger.warning("kg_update_failed", error=str(e))

    async def _handle_insufficient_evidence(self, claim: Claim, atomic_claims: list[AtomicClaim]) -> DebateResult:
        debate = await self.debate_logger.create_debate(claim.id)
        from app.domain.enums import AgentRole
        from app.domain.models import AgentResponse

        empty_response = AgentResponse(
            agent=AgentRole.JUDGE,
            reasoning="Insufficient evidence retrieved to verify this claim.",
            confidence=0.0,
            verdict=Verdict.INSUFFICIENT_EVIDENCE,
        )

        claim.overall_verdict = Verdict.INSUFFICIENT_EVIDENCE.value
        claim.overall_confidence = 0.0
        await self.debate_logger.finalize_debate(debate, Verdict.INSUFFICIENT_EVIDENCE.value, 0.0, True, 0.0, 0.0)
        await self.escalation.create_review(debate.id, claim.text, 0.0)

        return DebateResult(
            claim_id=claim.id,
            debate_id=debate.id,
            atomic_claims=atomic_claims,
            advocate=empty_response,
            skeptic=empty_response,
            judge=empty_response,
            overall_verdict=Verdict.INSUFFICIENT_EVIDENCE,
            overall_confidence=0.0,
            requires_human_review=True,
            evidence=[],
        )

    @staticmethod
    def _build_retrieval_query(claim_text: str, atomic_claims: list[AtomicClaim]) -> str:
        parts = [claim_text]
        for ac in atomic_claims[:3]:
            parts.append(f"{ac.subject} {ac.predicate} {ac.object}")
        return " ".join(parts)
