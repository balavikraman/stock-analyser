from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FilingSnapshot
from .official_facts import document_url, parse_datetime, source_key


def persist_filing_bundle(db: Session, bundle: dict[str, Any]) -> dict[str, int]:
    symbol = str(bundle.get("symbol") or "").upper()
    created = 0
    existing = 0
    for filing_type in ("announcements", "financial_results", "shareholding"):
        for row in bundle.get(filing_type) or []:
            if not isinstance(row, dict):
                continue
            key = source_key(symbol, filing_type, row)
            found = db.scalar(select(FilingSnapshot.id).where(
                FilingSnapshot.symbol == symbol,
                FilingSnapshot.source == "NSE",
                FilingSnapshot.filing_type == filing_type,
                FilingSnapshot.source_key == key,
            ))
            if found:
                existing += 1
                continue
            observed_raw = next((row.get(k) for k in ("broadcastDateTime", "broadcastDate", "submissionDate", "date") if row.get(k)), None)
            period = next((row.get(k) for k in ("periodEnded", "period_ended", "asOnDate", "as_on_date", "period") if row.get(k)), None)
            db.add(FilingSnapshot(
                symbol=symbol,
                source="NSE",
                filing_type=filing_type,
                source_key=key,
                observed_at=parse_datetime(observed_raw),
                period=str(period)[:64] if period else None,
                document_url=document_url(row),
                payload=row,
            ))
            created += 1
    db.commit()
    return {"created": created, "existing": existing}


def recent_filings(db: Session, symbol: str, limit: int = 100) -> list[FilingSnapshot]:
    return list(db.scalars(
        select(FilingSnapshot)
        .where(FilingSnapshot.symbol == symbol.upper())
        .order_by(FilingSnapshot.observed_at.desc(), FilingSnapshot.id.desc())
        .limit(max(1, min(limit, 500)))
    ).all())
