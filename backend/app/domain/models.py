from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.enums import (
    AgentRole,
    ChallengeType,
    HumanReviewStatus,
    KGEdgeStatus,
    Verdict,
    VerificationStatus,
)


class SourceRef(BaseModel):
    source_id: str
    title: str
    url: Optional[str] = None
    credibility: float = Field(ge=0.0, le=1.0, default=0.5)


class AtomicClaim(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    subject: str
    predicate: str
    object: str
    timestamp: Optional[datetime] = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    verification_status: VerificationStatus = VerificationStatus.PENDING
    parent_claim_id: Optional[UUID] = None
    weight: float = Field(ge=0.0, default=1.0)


class Evidence(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    content: str
    source_id: str
    source_title: str
    source_url: Optional[str] = None
    credibility: float = Field(ge=0.0, le=1.0, default=0.5)
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    fused_score: Optional[float] = None
    rerank_score: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Challenge(BaseModel):
    challenge_type: ChallengeType
    description: str
    reasoning: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class AgentContext(BaseModel):
    claim_text: str
    atomic_claim: Optional[AtomicClaim] = None
    evidence: list[Evidence] = Field(default_factory=list)
    advocate_response: Optional["AgentResponse"] = None
    skeptic_response: Optional["AgentResponse"] = None


class AgentResponse(BaseModel):
    agent: AgentRole
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)
    challenges: list[Challenge] = Field(default_factory=list)
    verdict: Optional[Verdict] = None
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    prompt: str = ""
    raw_response: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class JudgeResult(BaseModel):
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    evidence_used: list[str] = Field(default_factory=list)


class DebateResult(BaseModel):
    claim_id: UUID
    debate_id: UUID
    atomic_claims: list[AtomicClaim]
    advocate: AgentResponse
    skeptic: AgentResponse
    judge: AgentResponse
    overall_verdict: Verdict
    overall_confidence: float
    requires_human_review: bool
    evidence: list[Evidence]


class KGNode(BaseModel):
    entity_id: str
    name: str
    entity_type: str = "entity"
    properties: dict[str, Any] = Field(default_factory=dict)


class KGEdge(BaseModel):
    source_id: str
    target_id: str
    relationship: str
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    evidence_refs: list[str] = Field(default_factory=list)
    source_credibility: float = Field(ge=0.0, le=1.0, default=0.5)
    status: KGEdgeStatus = KGEdgeStatus.ACTIVE
    claim_id: Optional[str] = None


class Contradiction(BaseModel):
    existing_edge: KGEdge
    new_claim: AtomicClaim
    conflict_type: str
    status: KGEdgeStatus = KGEdgeStatus.UNRESOLVED


class TrainingSampleData(BaseModel):
    instruction: str
    claim: str
    evidence: list[str]
    correct_challenge: str
    judge_reasoning: str
    embedding: Optional[list[float]] = None


class HumanReviewItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    debate_id: UUID
    claim_text: str
    judge_confidence: float
    status: HumanReviewStatus = HumanReviewStatus.PENDING
    reviewer_notes: Optional[str] = None


class EvaluationMetrics(BaseModel):
    challenge_recall: float
    challenge_precision: float
    challenge_f1: float
    miss_rate: float
    avg_latency_ms: float
    avg_cost_usd: float
    model_name: str
    sample_count: int


AgentContext.model_rebuild()
