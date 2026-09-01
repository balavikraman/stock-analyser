from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ValidationRun
from .validation import update_prediction_outcomes


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _market_today() -> date:
    timezone_name = get_settings().validation_timezone
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError:
        return datetime.now(timezone.utc).date()


def validation_run_payload(row: ValidationRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_key": row.run_key,
        "run_date": row.run_date.isoformat(),
        "status": row.status,
        "triggered_by": row.triggered_by,
        "attempt": row.attempt,
        "requested_limit": row.requested_limit,
        "started_at": row.started_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "predictions_checked": row.predictions_checked,
        "outcomes": {
            "created": row.outcomes_created,
            "updated": row.outcomes_updated,
            "complete": row.outcomes_complete,
            "pending": row.outcomes_pending,
        },
        "errors": row.errors or [],
        "details": row.details or {},
    }


def _active_run(row: ValidationRun, now: datetime) -> bool:
    timeout = max(1, int(get_settings().validation_run_timeout_minutes))
    return row.status == "running" and row.started_at >= now - timedelta(minutes=timeout)


def execute_validation_run(
    db: Session,
    *,
    limit: int | None = None,
    force: bool = False,
    as_of: date | None = None,
    provider: Any | None = None,
    triggered_by: str = "api",
) -> dict[str, Any]:
    """Run at most one successful daily maturation job, with retryable failures.

    The unique daily run key makes a scheduled command idempotent. A failed or stale
    run may be retried; a completed one is skipped unless a user explicitly forces it.
    """
    run_date = as_of or _market_today()
    run_key = f"outcome-maturation:{run_date.isoformat()}"
    now = _utcnow()
    row = db.scalar(select(ValidationRun).where(ValidationRun.run_key == run_key))
    if row and row.status == "success" and not force:
        return {"execution": "skipped", "reason": "successful daily run already exists", "run": validation_run_payload(row)}
    if row and _active_run(row, now):
        return {"execution": "active", "reason": "another daily run is still active", "run": validation_run_payload(row)}

    if row is None:
        row = ValidationRun(
            run_key=run_key,
            run_date=run_date,
            status="running",
            triggered_by=triggered_by,
            attempt=1,
            requested_limit=limit,
            started_at=now,
            errors=[],
            details={},
        )
        db.add(row)
    else:
        row.status = "running"
        row.triggered_by = triggered_by
        row.attempt += 1
        row.requested_limit = limit
        row.started_at = now
        row.completed_at = None
        row.errors = []
        row.details = {}
    try:
        db.commit()
    except IntegrityError:
        # A second scheduler process inserted the same daily key between our read
        # and write. Treat that process as the owner rather than running twice.
        db.rollback()
        existing = db.scalar(select(ValidationRun).where(ValidationRun.run_key == run_key))
        if existing is not None:
            state = "skipped" if existing.status == "success" else "active"
            return {"execution": state, "reason": "daily run was claimed by another process", "run": validation_run_payload(existing)}
        raise
    db.refresh(row)

    try:
        summary = update_prediction_outcomes(db, provider=provider, as_of=as_of, limit=limit)
    except Exception as exc:
        # The outcome update may have left the SQLAlchemy transaction invalid.
        # Its run record was committed before processing, so it can be reloaded
        # and marked failed without losing the audit trail.
        db.rollback()
        row = db.get(ValidationRun, row.id)
        if row is None:
            raise
        row.status = "failed"
        row.completed_at = _utcnow()
        row.errors = [f"{type(exc).__name__}: {exc}"]
        row.details = {"random_split_used": False}
        db.commit()
        return {"execution": "failed", "run": validation_run_payload(row)}

    row.predictions_checked = int(summary.get("predictions_checked") or 0)
    row.outcomes_created = int(summary.get("outcomes_created") or 0)
    row.outcomes_updated = int(summary.get("outcomes_updated") or 0)
    row.outcomes_complete = int(summary.get("complete") or 0)
    row.outcomes_pending = int(summary.get("pending") or 0)
    row.errors = list(summary.get("errors") or [])
    row.details = {"as_of": summary.get("as_of"), "random_split_used": False}
    row.completed_at = _utcnow()
    row.status = "partial" if row.errors else "success"
    db.commit()
    db.refresh(row)
    return {"execution": row.status, "run": validation_run_payload(row)}


def validation_runner_status(db: Session) -> dict[str, Any]:
    settings = get_settings()
    rows = list(db.scalars(select(ValidationRun).order_by(ValidationRun.started_at.desc(), ValidationRun.id.desc()).limit(20)).all())
    latest = rows[0] if rows else None
    return {
        "enabled": True,
        "timezone": settings.validation_timezone,
        "daily_command": "python -m backend.app.jobs.validation_runner",
        "latest_run": validation_run_payload(latest) if latest else None,
        "recent_runs": [validation_run_payload(row) for row in rows],
    }
