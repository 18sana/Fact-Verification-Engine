"""Initial schema with pgvector extension."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("overall_verdict", sa.String(50), nullable=True),
        sa.Column("overall_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "atomic_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("predicate", sa.String(500), nullable=False),
        sa.Column("object", sa.String(500), nullable=False),
        sa.Column("claim_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_refs", postgresql.JSONB(), default=list),
        sa.Column("confidence", sa.Float(), default=0.0),
        sa.Column("weight", sa.Float(), default=1.0),
        sa.Column("verification_status", sa.String(50), default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("credibility", sa.Float(), default=0.5),
        sa.Column("source_type", sa.String(100), default="document"),
        sa.Column("metadata", postgresql.JSONB(), default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "debates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("verdict", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("requires_human_review", sa.Boolean(), default=False),
        sa.Column("total_latency_ms", sa.Float(), default=0.0),
        sa.Column("total_cost_usd", sa.Float(), default=0.0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "debate_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("debate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("agent", sa.String(50), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("retrieved_evidence", postgresql.JSONB(), default=list),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_ids", postgresql.JSONB(), default=list),
        sa.Column("latency_ms", sa.Float(), default=0.0),
        sa.Column("cost_usd", sa.Float(), default=0.0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("mlflow_run_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("teacher_model", sa.String(200), nullable=False),
        sa.Column("student_model", sa.String(200), nullable=False),
        sa.Column("config", postgresql.JSONB(), default=dict),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "training_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("debate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), default=list),
        sa.Column("correct_challenge", sa.Text(), nullable=False),
        sa.Column("judge_reasoning", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), default=False),
        sa.Column("human_approved", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "human_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("debate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("judge_confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "evaluation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("experiments.id"), nullable=True),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("challenge_recall", sa.Float(), nullable=False),
        sa.Column("challenge_precision", sa.Float(), nullable=False),
        sa.Column("challenge_f1", sa.Float(), nullable=False),
        sa.Column("miss_rate", sa.Float(), nullable=False),
        sa.Column("avg_latency_ms", sa.Float(), nullable=False),
        sa.Column("avg_cost_usd", sa.Float(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("metrics_detail", postgresql.JSONB(), default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_evidence_embedding", "evidence", ["embedding"], postgresql_using="ivfflat")


def downgrade() -> None:
    for table in [
        "evaluation_results", "human_reviews", "training_samples", "experiments",
        "debate_turns", "debates", "evidence", "sources", "atomic_claims", "claims", "users",
    ]:
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS vector")
