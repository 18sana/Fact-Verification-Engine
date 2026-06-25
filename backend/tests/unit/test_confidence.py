import math

import pytest

from app.domain.models import AtomicClaim
from app.services.confidence import ConfidenceService


class TestConfidenceService:
    def test_aggregate_equal_weights(self):
        result = ConfidenceService.aggregate_atomic([0.8, 0.9, 0.7], [1.0, 1.0, 1.0])
        assert 0.79 < result < 0.81

    def test_aggregate_weighted(self):
        result = ConfidenceService.aggregate_atomic([0.9, 0.5], [2.0, 1.0])
        assert result > 0.7

    def test_empty_confidences(self):
        assert ConfidenceService.aggregate_atomic([], []) == 0.0

    def test_from_atomic_claims(self):
        claims = [
            AtomicClaim(subject="A", predicate="p", object="o", confidence=0.8, weight=1.0),
            AtomicClaim(subject="B", predicate="p", object="o", confidence=0.9, weight=2.0),
        ]
        result = ConfidenceService.from_atomic_claims(claims)
        assert 0.0 < result <= 1.0

    def test_geometric_mean_property(self):
        # Equal confidences should return same value
        result = ConfidenceService.aggregate_atomic([0.5, 0.5, 0.5], [1.0, 1.0, 1.0])
        assert abs(result - 0.5) < 0.01

    def test_overall_from_atomic_and_judge(self):
        claims = [
            AtomicClaim(subject="A", predicate="p", object="o", confidence=0.8, weight=1.0),
            AtomicClaim(subject="B", predicate="p", object="o", confidence=0.6, weight=1.0),
        ]
        result = ConfidenceService.overall_from_atomic_and_judge(claims, 0.9)
        assert 0.0 < result <= 1.0
