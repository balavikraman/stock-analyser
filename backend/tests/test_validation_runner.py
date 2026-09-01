from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db import Base
from backend.app.models import ValidationRun
from backend.app.services import validation_runner
from backend.app.services.validation_runner import execute_validation_run, validation_runner_status


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_daily_runner_is_idempotent_after_a_success(monkeypatch):
    db = _session()
    calls: list[dict] = []

    def complete(_db, **kwargs):
        calls.append(kwargs)
        return {"predictions_checked": 3, "outcomes_created": 2, "outcomes_updated": 1, "complete": 2, "pending": 1, "errors": [], "as_of": "2026-01-12"}

    monkeypatch.setattr(validation_runner, "update_prediction_outcomes", complete)
    first = execute_validation_run(db, as_of=date(2026, 1, 12), triggered_by="test")
    second = execute_validation_run(db, as_of=date(2026, 1, 12), triggered_by="test")

    assert first["execution"] == "success"
    assert first["run"]["attempt"] == 1
    assert second["execution"] == "skipped"
    assert len(calls) == 1
    assert db.query(ValidationRun).count() == 1


def test_failed_run_can_be_retried_and_keeps_attempt_history(monkeypatch):
    db = _session()

    def failing(_db, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(validation_runner, "update_prediction_outcomes", failing)
    failed = execute_validation_run(db, as_of=date(2026, 1, 13), triggered_by="test")
    assert failed["execution"] == "failed"
    assert failed["run"]["errors"] == ["RuntimeError: provider unavailable"]

    monkeypatch.setattr(validation_runner, "update_prediction_outcomes", lambda _db, **_kwargs: {"predictions_checked": 0, "outcomes_created": 0, "outcomes_updated": 0, "complete": 0, "pending": 0, "errors": [], "as_of": "2026-01-13"})
    retried = execute_validation_run(db, as_of=date(2026, 1, 13), triggered_by="test")

    assert retried["execution"] == "success"
    assert retried["run"]["attempt"] == 2
    assert db.query(ValidationRun).count() == 1


def test_partial_run_preserves_provider_errors_and_status_exposes_them(monkeypatch):
    db = _session()
    monkeypatch.setattr(validation_runner, "update_prediction_outcomes", lambda _db, **_kwargs: {"predictions_checked": 4, "outcomes_created": 1, "outcomes_updated": 0, "complete": 1, "pending": 3, "errors": ["INFY.NS price history unavailable: TimeoutError"], "as_of": "2026-01-14"})

    result = execute_validation_run(db, as_of=date(2026, 1, 14), triggered_by="test")
    status = validation_runner_status(db)

    assert result["execution"] == "partial"
    assert result["run"]["outcomes"]["pending"] == 3
    assert status["latest_run"]["status"] == "partial"
    assert status["latest_run"]["errors"] == ["INFY.NS price history unavailable: TimeoutError"]


def test_active_run_is_never_overridden_even_when_force_is_requested(monkeypatch):
    db = _session()
    db.add(ValidationRun(
        run_key="outcome-maturation:2026-01-15", run_date=date(2026, 1, 15),
        status="running", triggered_by="cli", attempt=1,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None), errors=[], details={},
    ))
    db.commit()
    monkeypatch.setattr(validation_runner, "update_prediction_outcomes", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not execute")))

    result = execute_validation_run(db, as_of=date(2026, 1, 15), force=True, triggered_by="test")

    assert result["execution"] == "active"
