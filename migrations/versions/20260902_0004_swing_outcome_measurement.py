from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260902_0004"
down_revision = "20260901_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("prediction_outcomes")}
    if "target_price" not in columns:
        op.add_column("prediction_outcomes", sa.Column("target_price", sa.Float(), nullable=True))
    if "stop_price" not in columns:
        op.add_column("prediction_outcomes", sa.Column("stop_price", sa.Float(), nullable=True))
    if "target_stop_status" not in columns:
        op.add_column("prediction_outcomes", sa.Column("target_stop_status", sa.String(length=48), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("prediction_outcomes")}
    for name in ("target_stop_status", "stop_price", "target_price"):
        if name in columns:
            op.drop_column("prediction_outcomes", name)
