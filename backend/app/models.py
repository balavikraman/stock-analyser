from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AnalysisSnapshot(Base):
    __tablename__ = "analysis_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String(64), default="INSUFFICIENT DATA")
    payload: Mapped[dict] = mapped_column(JSON)


class FilingSnapshot(Base):
    __tablename__ = "filing_snapshots"
    __table_args__ = (UniqueConstraint("symbol", "source", "filing_type", "source_key", name="uq_filing_source_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    filing_type: Mapped[str] = mapped_column(String(64), index=True)
    source_key: Mapped[str] = mapped_column(String(255))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
    period: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(32))
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    thesis: Mapped[str] = mapped_column(Text, default="")
    thesis_breaker: Mapped[str] = mapped_column(Text, default="")
    snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    target_entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class PredictionRecord(Base):
    __tablename__ = "prediction_records"
    __table_args__ = (UniqueConstraint("snapshot_id", "strategy", "model_version", name="uq_prediction_snapshot_strategy_model"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    strategy: Mapped[str] = mapped_column(String(32), index=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    model_frozen: Mapped[bool] = mapped_column(Boolean, default=True)
    signal: Mapped[str] = mapped_column(String(64), index=True)
    actionable: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    validation_eligible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark_symbol: Mapped[str] = mapped_column(String(32), default="^NSEI")
    data_quality_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    model_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    horizon_spec: Mapped[dict] = mapped_column(JSON)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_snapshots.id"), nullable=True, index=True)
    input_snapshot: Mapped[dict] = mapped_column(JSON)


class PredictionOutcome(Base):
    __tablename__ = "prediction_outcomes"
    __table_args__ = (UniqueConstraint("prediction_id", "horizon_days", name="uq_prediction_outcome_horizon"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("prediction_records.id", ondelete="CASCADE"), index=True)
    horizon_label: Mapped[str] = mapped_column(String(16))
    horizon_days: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    start_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_cost_pct: Mapped[float] = mapped_column(Float, default=0.0)
    net_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    excess_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_favorable_excursion_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_adverse_excursion_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # These are outcome measurements for the frozen swing baseline.  They are
    # deliberately not trade instructions and never infer an intraday ordering
    # when the daily bar touched both levels.
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_stop_status: Mapped[str | None] = mapped_column(String(48), nullable=True)
    price_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ValidationRun(Base):
    """One idempotent daily attempt to mature prospective prediction outcomes."""

    __tablename__ = "validation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_key: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    run_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    triggered_by: Mapped[str] = mapped_column(String(32), default="api")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    requested_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    predictions_checked: Mapped[int] = mapped_column(Integer, default=0)
    outcomes_created: Mapped[int] = mapped_column(Integer, default=0)
    outcomes_updated: Mapped[int] = mapped_column(Integer, default=0)
    outcomes_complete: Mapped[int] = mapped_column(Integer, default=0)
    outcomes_pending: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
