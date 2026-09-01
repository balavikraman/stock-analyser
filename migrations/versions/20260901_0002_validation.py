from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260901_0002"
down_revision = "20260901_0001"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "prediction_records" not in tables:
        op.create_table(
            "prediction_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("strategy", sa.String(length=32), nullable=False),
            sa.Column("model_version", sa.String(length=64), nullable=False),
            sa.Column("model_frozen", sa.Boolean(), nullable=False),
            sa.Column("signal", sa.String(length=64), nullable=False),
            sa.Column("actionable", sa.Boolean(), nullable=False),
            sa.Column("validation_eligible", sa.Boolean(), nullable=False),
            sa.Column("entry_price", sa.Float(), nullable=True),
            sa.Column("benchmark_symbol", sa.String(length=32), nullable=False),
            sa.Column("data_quality_confidence", sa.Float(), nullable=False),
            sa.Column("model_probability", sa.Float(), nullable=True),
            sa.Column("decision_confidence", sa.Float(), nullable=False),
            sa.Column("horizon_spec", sa.JSON(), nullable=False),
            sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("analysis_snapshots.id"), nullable=True),
            sa.Column("input_snapshot", sa.JSON(), nullable=False),
            sa.UniqueConstraint("snapshot_id", "strategy", "model_version", name="uq_prediction_snapshot_strategy_model"),
        )
        for column in ("created_at", "symbol", "strategy", "model_version", "signal", "actionable", "validation_eligible", "snapshot_id"):
            op.create_index(f"ix_prediction_records_{column}", "prediction_records", [column])

    tables = _tables()
    if "prediction_outcomes" not in tables:
        op.create_table(
            "prediction_outcomes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("prediction_id", sa.Integer(), sa.ForeignKey("prediction_records.id", ondelete="CASCADE"), nullable=False),
            sa.Column("horizon_label", sa.String(length=16), nullable=False),
            sa.Column("horizon_days", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("evaluated_at", sa.DateTime(), nullable=True),
            sa.Column("start_date", sa.DateTime(), nullable=True),
            sa.Column("end_date", sa.DateTime(), nullable=True),
            sa.Column("start_price", sa.Float(), nullable=True),
            sa.Column("end_price", sa.Float(), nullable=True),
            sa.Column("gross_return_pct", sa.Float(), nullable=True),
            sa.Column("estimated_cost_pct", sa.Float(), nullable=False),
            sa.Column("net_return_pct", sa.Float(), nullable=True),
            sa.Column("benchmark_return_pct", sa.Float(), nullable=True),
            sa.Column("excess_return_pct", sa.Float(), nullable=True),
            sa.Column("max_favorable_excursion_pct", sa.Float(), nullable=True),
            sa.Column("max_adverse_excursion_pct", sa.Float(), nullable=True),
            sa.Column("price_source", sa.String(length=64), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.UniqueConstraint("prediction_id", "horizon_days", name="uq_prediction_outcome_horizon"),
        )
        for column in ("prediction_id", "horizon_days", "status", "evaluated_at"):
            op.create_index(f"ix_prediction_outcomes_{column}", "prediction_outcomes", [column])


def downgrade() -> None:
    tables = _tables()
    if "prediction_outcomes" in tables:
        op.drop_table("prediction_outcomes")
    if "prediction_records" in tables:
        op.drop_table("prediction_records")
