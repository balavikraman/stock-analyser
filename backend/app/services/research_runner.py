from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ValidationRun
from .analyzer import StockAnalyzer
from .validation_runner import _market_today, validation_run_payload


def execute_research_run(db: Session, *, triggered_by: str = "api") -> dict:
    run_date = _market_today(); key = f"daily-research:{run_date.isoformat()}"
    row = db.scalar(select(ValidationRun).where(ValidationRun.run_key == key))
    if row and row.status == "success":
        return {"execution": "skipped", "reason": "successful daily research run already exists", "run": validation_run_payload(row)}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row is None:
        row = ValidationRun(run_key=key, run_date=run_date, status="running", triggered_by=triggered_by, attempt=1, started_at=now, errors=[], details={}); db.add(row)
    else:
        row.status="running"; row.attempt += 1; row.started_at=now; row.errors=[]; row.details={}
    db.commit()
    results=[]; errors=[]
    for symbol in get_settings().watchlist_symbols[:30]:
        try:
            report=StockAnalyzer().analyze(symbol)
            results.append({"symbol":symbol,"actionable":bool(report.entry_plan.get("actionable")),"verdict":report.verdict,"score":report.overall_score})
        except Exception as exc:
            errors.append(f"{symbol}: {type(exc).__name__}")
    row.predictions_checked=len(results); row.errors=errors; row.details={"actionable":sum(r["actionable"] for r in results),"blocked":sum(not r["actionable"] for r in results),"results":results}; row.completed_at=datetime.now(timezone.utc).replace(tzinfo=None); row.status="partial" if errors else "success"; db.commit(); db.refresh(row)
    return {"execution":row.status,"run":validation_run_payload(row)}


def research_runner_status(db: Session) -> dict:
    rows=list(db.scalars(select(ValidationRun).where(ValidationRun.run_key.like("daily-research:%")).order_by(ValidationRun.started_at.desc()).limit(10)).all())
    latest=rows[0] if rows else None
    today=_market_today().isoformat()
    state="NOT_RUN" if latest is None else ("STALE" if latest.run_date.isoformat()!=today else latest.status.upper())
    return {"status":state,"expected_date":today,"latest_run":validation_run_payload(latest) if latest else None,"recent_runs":[validation_run_payload(r) for r in rows]}
