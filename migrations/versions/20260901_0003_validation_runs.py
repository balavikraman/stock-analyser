from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260901_0003"
down_revision = "20260901_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "validation_runs" in tables:
        return
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_key", sa.String(length=96), nullable=False, unique=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("triggered_by", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("predictions_checked", sa.Integer(), nullable=False),
        sa.Column("outcomes_created", sa.Integer(), nullable=False),
        sa.Column("outcomes_updated", sa.Integer(), nullable=False),
        sa.Column("outcomes_complete", sa.Integer(), nullable=False),
        sa.Column("outcomes_pending", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    for column in ("run_key", "run_date", "status", "started_at", "completed_at"):
        op.create_index(f"ix_validation_runs_{column}", "validation_runs", [column])


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "validation_runs" in tables:
        op.drop_table("validation_runs")
