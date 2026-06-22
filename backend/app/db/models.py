import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.session import Base

settings = get_settings()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    claims: Mapped[list["Claim"]] = relationship(back_populates="user")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    overall_verdict: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    overall_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="claims")
    atomic_claims: Mapped[list["AtomicClaimDB"]] = relationship(back_populates="parent_claim", cascade="all, delete-orphan")
    debates: Mapped[list["Debate"]] = relationship(back_populates="claim", cascade="all, delete-orphan")


class AtomicClaimDB(Base):
    __tablename__ = "atomic_claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    predicate: Mapped[str] = mapped_column(String(500), nullable=False)
    object: Mapped[str] = mapped_column(String(500), nullable=False)
    claim_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_refs: Mapped[dict] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    verification_status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    parent_claim: Mapped["Claim"] = relationship(back_populates="atomic_claims")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    credibility: Mapped[float] = mapped_column(Float, default=0.5)
    source_type: Mapped[str] = mapped_column(String(100), default="document")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evidence_items: Mapped[list["EvidenceDB"]] = relationship(back_populates="source")


class EvidenceDB(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(settings.embedding_dimension), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped["Source"] = relationship(back_populates="evidence_items")


class Debate(Base):
    __tablename__ = "debates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    verdict: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="debates")
    turns: Mapped[list["DebateTurn"]] = relationship(back_populates="debate", cascade="all, delete-orphan")
    human_reviews: Mapped[list["HumanReview"]] = relationship(back_populates="debate", cascade="all, delete-orphan")


class DebateTurn(Base):
    __tablename__ = "debate_turns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("debates.id"), nullable=False)
    agent: Mapped[str] = mapped_column(String(50), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_evidence: Mapped[dict] = mapped_column(JSONB, default=list)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_ids: Mapped[dict] = mapped_column(JSONB, default=list)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    debate: Mapped["Debate"] = relationship(back_populates="turns")


class TrainingSample(Base):
    __tablename__ = "training_samples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("debates.id"), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, default=list)
    correct_challenge: Mapped[str] = mapped_column(Text, nullable=False)
    judge_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(settings.embedding_dimension), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    human_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("debates.id"), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    judge_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    debate: Mapped["Debate"] = relationship(back_populates="human_reviews")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("experiments.id"), nullable=True)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    challenge_recall: Mapped[float] = mapped_column(Float, nullable=False)
    challenge_precision: Mapped[float] = mapped_column(Float, nullable=False)
    challenge_f1: Mapped[float] = mapped_column(Float, nullable=False)
    miss_rate: Mapped[float] = mapped_column(Float, nullable=False)
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    experiment: Mapped[Optional["Experiment"]] = relationship(back_populates="evaluation_results")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mlflow_run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    teacher_model: Mapped[str] = mapped_column(String(200), nullable=False)
    student_model: Mapped[str] = mapped_column(String(200), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluation_results: Mapped[list["EvaluationResult"]] = relationship(back_populates="experiment")


class AdversarialEvalRun(Base):
    __tablename__ = "adversarial_eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    total_claims: Mapped[int] = mapped_column(Integer, nullable=False)
    challenges_detected: Mapped[int] = mapped_column(Integer, nullable=False)
    miss_rate: Mapped[float] = mapped_column(Float, nullable=False)
    attack_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False, default="base_skeptic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
