from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260901_0001"
down_revision = None
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()

    if "analysis_snapshots" not in tables:
        op.create_table(
            "analysis_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("overall_score", sa.Float(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("verdict", sa.String(length=64), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
        )
        op.create_index("ix_analysis_snapshots_symbol", "analysis_snapshots", ["symbol"])
        op.create_index("ix_analysis_snapshots_created_at", "analysis_snapshots", ["created_at"])

    tables = _tables()
    if "journal_entries" not in tables:
        op.create_table(
            "journal_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("price", sa.Float(), nullable=True),
            sa.Column("quantity", sa.Float(), nullable=True),
            sa.Column("thesis", sa.Text(), nullable=False),
            sa.Column("thesis_breaker", sa.Text(), nullable=False),
            sa.Column("snapshot_id", sa.Integer(), nullable=True),
        )
        op.create_index("ix_journal_entries_symbol", "journal_entries", ["symbol"])
        op.create_index("ix_journal_entries_created_at", "journal_entries", ["created_at"])

    tables = _tables()
    if "watchlist_items" not in tables:
        op.create_table(
            "watchlist_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("target_entry", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("symbol", name="uq_watchlist_items_symbol"),
        )
        op.create_index("ix_watchlist_items_symbol", "watchlist_items", ["symbol"], unique=True)

    tables = _tables()
    if "filing_snapshots" not in tables:
        op.create_table(
            "filing_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("source", sa.String(length=64), nullable=False),
            sa.Column("filing_type", sa.String(length=64), nullable=False),
            sa.Column("source_key", sa.String(length=255), nullable=False),
            sa.Column("observed_at", sa.DateTime(), nullable=True),
            sa.Column("fetched_at", sa.DateTime(), nullable=False),
            sa.Column("period", sa.String(length=64), nullable=True),
            sa.Column("document_url", sa.Text(), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.UniqueConstraint("symbol", "source", "filing_type", "source_key", name="uq_filing_source_key"),
        )
        op.create_index("ix_filing_snapshots_symbol", "filing_snapshots", ["symbol"])
        op.create_index("ix_filing_snapshots_source", "filing_snapshots", ["source"])
        op.create_index("ix_filing_snapshots_filing_type", "filing_snapshots", ["filing_type"])
        op.create_index("ix_filing_snapshots_observed_at", "filing_snapshots", ["observed_at"])
        op.create_index("ix_filing_snapshots_fetched_at", "filing_snapshots", ["fetched_at"])


def downgrade() -> None:
    tables = _tables()
    for table in ("filing_snapshots", "watchlist_items", "journal_entries", "analysis_snapshots"):
        if table in tables:
            op.drop_table(table)
