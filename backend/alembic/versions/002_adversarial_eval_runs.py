"""Add adversarial_eval_runs table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_adversarial_eval_runs"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "adversarial_eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("total_claims", sa.Integer(), nullable=False),
        sa.Column("challenges_detected", sa.Integer(), nullable=False),
        sa.Column("miss_rate", sa.Float(), nullable=False),
        sa.Column("attack_breakdown", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("model_name", sa.String(200), nullable=False, server_default="base_skeptic"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("adversarial_eval_runs")
