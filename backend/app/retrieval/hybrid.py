import json
import math
from typing import Optional
from uuid import UUID

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.models import Evidence

logger = get_logger(__name__)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class EmbeddingService:
    """Sentence-transformer embeddings with optional Redis cache."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._model = None
        self._redis: Optional[aioredis.Redis] = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.settings.embedding_model)
        return self._model

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self.settings.redis_url, decode_responses=True)
        return self._redis

    async def embed(self, texts: list[str]) -> np.ndarray:
        cache = await self._get_redis()
        results = []
        uncached_texts = []
        uncached_indices = []

        for i, t in enumerate(texts):
            cache_key = f"emb:{hash(t)}"
            cached = await cache.get(cache_key)
            if cached:
                results.append((i, json.loads(cached)))
            else:
                uncached_texts.append(t)
                uncached_indices.append(i)

        if uncached_texts:
            model = self._get_model()
            embeddings = model.encode(uncached_texts, normalize_embeddings=True)
            for idx, emb, txt in zip(uncached_indices, embeddings, uncached_texts):
                emb_list = emb.tolist()
                results.append((idx, emb_list))
                cache_key = f"emb:{hash(txt)}"
                await cache.setex(cache_key, self.settings.cache_ttl_seconds, json.dumps(emb_list))

        results.sort(key=lambda x: x[0])
        return np.array([r[1] for r in results])


class DenseRetriever:
    def __init__(self, embedding_service: EmbeddingService, settings: Optional[Settings] = None):
        self.embedding_service = embedding_service
        self.settings = settings or get_settings()

    async def retrieve(self, session: AsyncSession, query: str, top_k: int) -> list[tuple[Evidence, float]]:
        query_embedding = (await self.embedding_service.embed([query]))[0]
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        sql = text("""
            SELECT e.id, e.content, e.source_id, s.title, s.url, s.credibility,
                   1 - (e.embedding <=> CAST(:embedding AS vector)) AS score
            FROM evidence e
            JOIN sources s ON e.source_id = s.id
            WHERE e.embedding IS NOT NULL
            ORDER BY e.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """)

        result = await session.execute(sql, {"embedding": embedding_str, "top_k": top_k})
        rows = result.fetchall()

        evidence_list = []
        for row in rows:
            ev = Evidence(
                id=row.id,
                content=row.content,
                source_id=str(row.source_id),
                source_title=row.title,
                source_url=row.url,
                credibility=row.credibility,
                dense_score=float(row.score),
            )
            evidence_list.append((ev, float(row.score)))
        return evidence_list


class SparseRetriever:
    """BM25 sparse retrieval over in-memory corpus loaded from DB."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._bm25 = None
        self._corpus: list[Evidence] = []
        self._tokenized_corpus: list[list[str]] = []

    def _tokenize(self, text: str) -> list[str]:
        return text.lower().split()

    async def build_index(self, session: AsyncSession) -> None:
        from rank_bm25 import BM25Okapi

        from app.db.models import EvidenceDB, Source

        stmt = select(EvidenceDB, Source).join(Source, EvidenceDB.source_id == Source.id)
        result = await session.execute(stmt)
        rows = result.all()

        self._corpus = []
        self._tokenized_corpus = []
        for ev_db, source in rows:
            ev = Evidence(
                id=ev_db.id,
                content=ev_db.content,
                source_id=str(ev_db.source_id),
                source_title=source.title,
                source_url=source.url,
                credibility=source.credibility,
            )
            self._corpus.append(ev)
            self._tokenized_corpus.append(self._tokenize(ev_db.content))

        if self._tokenized_corpus:
            self._bm25 = BM25Okapi(self._tokenized_corpus)
        else:
            self._bm25 = None

    async def retrieve(self, query: str, top_k: int) -> list[tuple[Evidence, float]]:
        if not self._bm25 or not self._corpus:
            return []

        tokenized_query = self._tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                ev = self._corpus[idx].model_copy()
                ev.sparse_score = float(scores[idx])
                results.append((ev, float(scores[idx])))
        return results


class ScoreFusion:
    """Reciprocal Rank Fusion to merge dense and sparse results."""

    def __init__(self, k: int = 60):
        self.k = k

    def fuse(
        self,
        dense_results: list[tuple[Evidence, float]],
        sparse_results: list[tuple[Evidence, float]],
    ) -> list[Evidence]:
        scores: dict[UUID, float] = {}
        evidence_map: dict[UUID, Evidence] = {}

        for rank, (ev, _) in enumerate(dense_results):
            key = ev.id
            scores[key] = scores.get(key, 0.0) + 1.0 / (self.k + rank + 1)
            evidence_map[key] = ev

        for rank, (ev, _) in enumerate(sparse_results):
            key = ev.id
            scores[key] = scores.get(key, 0.0) + 1.0 / (self.k + rank + 1)
            if key not in evidence_map:
                evidence_map[key] = ev

        sorted_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
        fused = []
        for key in sorted_keys:
            ev = evidence_map[key].model_copy()
            ev.fused_score = scores[key]
            fused.append(ev)
        return fused


class CrossEncoderReranker:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.settings.cross_encoder_model)
        return self._model

    def rerank(self, query: str, evidence_list: list[Evidence], top_k: int) -> list[Evidence]:
        if not evidence_list:
            return []

        model = self._get_model()
        pairs = [[query, ev.content] for ev in evidence_list]
        scores = model.predict(pairs)

        scored = list(zip(evidence_list, scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        reranked = []
        for ev, score in scored[:top_k]:
            ev_copy = ev.model_copy()
            ev_copy.rerank_score = _sigmoid(float(score))
            reranked.append(ev_copy)
        return reranked


class HybridRetrievalService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Optional[Settings] = None,
    ):
        self.session = session
        self.settings = settings or get_settings()
        self.embedding_service = EmbeddingService(self.settings)
        self.dense_retriever = DenseRetriever(self.embedding_service, self.settings)
        self.sparse_retriever = SparseRetriever(self.settings)
        self.fusion = ScoreFusion(k=self.settings.rrf_k)
        self.reranker = CrossEncoderReranker(self.settings)
        self._index_built = False

    async def _ensure_index(self) -> None:
        if not self._index_built:
            await self.sparse_retriever.build_index(self.session)
            self._index_built = True

    async def retrieve(self, query: str, top_k: Optional[int] = None) -> list[Evidence]:
        await self._ensure_index()
        k = top_k or self.settings.rerank_top_k
        retrieval_k = self.settings.retrieval_top_k

        dense_results = await self.dense_retriever.retrieve(self.session, query, retrieval_k)
        sparse_results = await self.sparse_retriever.retrieve(query, retrieval_k)

        if not dense_results and not sparse_results:
            logger.warning("no_retrieval_results", query=query)
            return []

        fused = self.fusion.fuse(dense_results, sparse_results)
        reranked = self.reranker.rerank(query, fused, k)
        min_score = self.settings.min_relevance_score
        relevant = [ev for ev in reranked if (ev.rerank_score or 0.0) >= min_score]
        if not relevant and reranked:
            logger.warning(
                "retrieval_below_relevance_threshold",
                query=query,
                top_score=reranked[0].rerank_score,
                threshold=min_score,
            )
        logger.info("retrieval_complete", query=query, count=len(relevant))
        return relevant
