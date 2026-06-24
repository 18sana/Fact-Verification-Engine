import math
from typing import Sequence

from app.domain.models import AtomicClaim, Evidence


class ConfidenceService:
    """Mathematical confidence propagation using weighted geometric mean."""

    @staticmethod
    def aggregate_atomic(confidences: Sequence[float], weights: Sequence[float]) -> float:
        if not confidences:
            return 0.0
        if len(confidences) != len(weights):
            weights = [1.0] * len(confidences)

        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0

        log_sum = sum(w * math.log(max(c, 1e-10)) for c, w in zip(confidences, weights))
        return math.exp(log_sum / total_weight)

    @staticmethod
    def from_atomic_claims(claims: Sequence[AtomicClaim]) -> float:
        confidences = [c.confidence for c in claims]
        weights = [c.weight for c in claims]
        return ConfidenceService.aggregate_atomic(confidences, weights)

    @staticmethod
    def evidence_score_for_claim(atomic: AtomicClaim, evidence: Sequence[Evidence]) -> float:
        """Estimate per-atomic confidence from retrieval relevance scores."""
        if not evidence:
            return 0.0
        keywords = {atomic.subject.lower(), atomic.object.lower(), atomic.predicate.lower()}
        relevant_scores = []
        for ev in evidence:
            content_lower = ev.content.lower()
            if any(k and k in content_lower for k in keywords):
                score = ev.rerank_score or ev.fused_score or ev.dense_score or 0.5
                relevant_scores.append(float(score))
        if not relevant_scores:
            relevant_scores = [
                float(ev.rerank_score or ev.fused_score or ev.dense_score or 0.5) for ev in evidence
            ]
        return sum(relevant_scores) / len(relevant_scores)

    @staticmethod
    def propagate_to_atomic_claims(
        claims: list[AtomicClaim],
        evidence: list[Evidence],
        judge_confidence: float,
    ) -> list[AtomicClaim]:
        """Blend evidence-based sub-claim confidence with judge score, then usable for aggregation."""
        for claim in claims:
            ev_score = ConfidenceService.evidence_score_for_claim(claim, evidence)
            # Bottom-up: sub-claim confidence from evidence, tempered by judge
            claim.confidence = max(0.0, min(1.0, 0.6 * ev_score + 0.4 * judge_confidence))
        return claims

    @staticmethod
    def overall_from_atomic_and_judge(
        claims: Sequence[AtomicClaim],
        judge_confidence: float,
    ) -> float:
        """Parent confidence = geometric mean of atomic confidences, blended with judge."""
        atomic_overall = ConfidenceService.from_atomic_claims(claims)
        if not claims:
            return judge_confidence
        # 70% propagated from sub-claims, 30% judge anchor
        return max(0.0, min(1.0, 0.7 * atomic_overall + 0.3 * judge_confidence))
