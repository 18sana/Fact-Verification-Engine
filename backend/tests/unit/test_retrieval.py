from uuid import uuid4

import pytest

from app.domain.models import Evidence
from app.retrieval.hybrid import ScoreFusion


class TestScoreFusion:
    def test_fuse_combines_results(self):
        fusion = ScoreFusion(k=60)
        ev1 = Evidence(id=uuid4(), content="test one", source_id="s1", source_title="Source 1")
        ev2 = Evidence(id=uuid4(), content="test two", source_id="s2", source_title="Source 2")

        dense = [(ev1, 0.9), (ev2, 0.7)]
        sparse = [(ev2, 0.8), (ev1, 0.6)]

        fused = fusion.fuse(dense, sparse)
        assert len(fused) == 2
        assert fused[0].fused_score is not None
        assert fused[0].fused_score >= fused[1].fused_score

    def test_fuse_empty(self):
        fusion = ScoreFusion()
        assert fusion.fuse([], []) == []

    def test_fuse_single_source(self):
        fusion = ScoreFusion()
        ev = Evidence(id=uuid4(), content="only", source_id="s1", source_title="S")
        fused = fusion.fuse([(ev, 0.9)], [])
        assert len(fused) == 1
