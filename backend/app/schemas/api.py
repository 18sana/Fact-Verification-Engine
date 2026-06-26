from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import Verdict


class VerifyClaimRequest(BaseModel):
    claim: str = Field(..., min_length=3, max_length=5000)
    user_id: Optional[UUID] = None


class AtomicClaimResponse(BaseModel):
    id: UUID
    subject: str
    predicate: str
    object: str
    confidence: float
    verification_status: str


class AgentResponseSchema(BaseModel):
    agent: str
    reasoning: str
    confidence: float
    sources: list[str] = []
    challenges: list[dict[str, Any]] = []
    evidence_used: list[str] = []
    verdict: Optional[str] = None
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class EvidenceSchema(BaseModel):
    id: UUID
    content: str
    source_title: str
    source_url: Optional[str] = None
    credibility: float
    rerank_score: Optional[float] = None


class VerifyClaimResponse(BaseModel):
    claim_id: UUID
    debate_id: UUID
    overall_verdict: Verdict
    overall_confidence: float
    requires_human_review: bool
    atomic_claims: list[AtomicClaimResponse]
    advocate: AgentResponseSchema
    skeptic: AgentResponseSchema
    judge: AgentResponseSchema
    evidence: list[EvidenceSchema]


class DebateSummary(BaseModel):
    id: UUID
    claim_id: UUID
    verdict: Optional[str]
    confidence: Optional[float]
    requires_human_review: bool
    total_latency_ms: float
    total_cost_usd: float
    created_at: datetime


class DebateListResponse(BaseModel):
    debates: list[DebateSummary]
    total: int


class DebateDetailResponse(BaseModel):
    id: UUID
    claim_id: UUID
    verdict: Optional[str]
    confidence: Optional[float]
    requires_human_review: bool
    turns: list[dict[str, Any]]
    created_at: datetime


class KnowledgeGraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class TrainingStatsResponse(BaseModel):
    total_samples: int
    eligible_samples: int
    duplicates_rejected: int
    human_approved: int
    training_blocked: bool = False
    training_block_reason: Optional[str] = None


class HumanReviewItem(BaseModel):
    id: UUID
    debate_id: UUID
    claim_text: str
    judge_confidence: float
    status: str
    created_at: datetime


class HumanReviewListResponse(BaseModel):
    reviews: list[HumanReviewItem]
    total: int


class HumanReviewActionRequest(BaseModel):
    notes: Optional[str] = None


class AdversarialRunResponse(BaseModel):
    run_id: str
    total_claims: int
    challenges_detected: int
    miss_rate: float
    attack_breakdown: dict[str, Any]
    model_name: str


class AdversarialHistoryResponse(BaseModel):
    runs: list[dict[str, Any]]


class FineTuningStartRequest(BaseModel):
    name: str = "skeptic-qlora-run"


class FineTuningStartResponse(BaseModel):
    experiment_id: str
    status: str
    message: Optional[str] = None


class EvaluationMetricsResponse(BaseModel):
    challenge_recall: float
    challenge_precision: float
    challenge_f1: float
    miss_rate: float
    avg_latency_ms: float
    avg_cost_usd: float
    model_name: str
    sample_count: int


class EvaluationComparisonItem(BaseModel):
    model: str
    challenge_recall: float
    challenge_precision: float
    challenge_f1: float
    miss_rate: float
    avg_latency_ms: float
    avg_cost_usd: float
    sample_count: int
    created_at: str
    inference_model: Optional[str] = None


class EvaluationCompareResponse(BaseModel):
    comparisons: list[EvaluationComparisonItem]
    has_base: bool = False
    has_finetuned: bool = False


class FineTuningStatusResponse(BaseModel):
    experiments: list[dict[str, Any]]
    training_blocked: bool = False
    training_block_reason: Optional[str] = None
    finetuned_path: Optional[str] = None
    use_finetuned_skeptic: bool = False


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    services: dict[str, str]
