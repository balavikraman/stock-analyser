from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class EvidenceRecord:
    value: Any
    source: str
    source_type: str
    observed_at: str | None = None
    period: str | None = None
    fetched_at: str | None = None
    confidence: float = 0.5
    stale_after_days: int | None = None
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data["fetched_at"] is None:
            data["fetched_at"] = datetime.now(timezone.utc).isoformat()
        data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))
        return data


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def stale_status(observed_at: str | None, stale_after_days: int | None, now: datetime | None = None) -> dict[str, Any]:
    if not stale_after_days:
        return {"is_stale": False, "age_days": None, "reason": None}
    observed = parse_datetime(observed_at)
    if observed is None:
        return {"is_stale": True, "age_days": None, "reason": "missing observation timestamp"}
    current = now or datetime.now(timezone.utc)
    age_days = max(0.0, (current - observed).total_seconds() / 86400)
    is_stale = age_days > stale_after_days
    return {
        "is_stale": is_stale,
        "age_days": round(age_days, 2),
        "reason": f"older than {stale_after_days} days" if is_stale else None,
    }


def summarize_evidence(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    total = len(evidence)
    if total == 0:
        return {
            "evidence_items": 0,
            "stale_items": 0,
            "verified_items": 0,
            "evidence_confidence": 0.0,
            "stale_keys": [],
        }

    stale_keys: list[str] = []
    confidence_sum = 0.0
    verified = 0
    for key, item in evidence.items():
        status = stale_status(item.get("observed_at") or item.get("fetched_at"), item.get("stale_after_days"))
        if status["is_stale"]:
            stale_keys.append(key)
        confidence = float(item.get("confidence") or 0)
        if status["is_stale"]:
            confidence *= 0.35
        confidence_sum += confidence
        if item.get("source") and item.get("source_type") not in {"demo", "unknown"}:
            verified += 1

    return {
        "evidence_items": total,
        "stale_items": len(stale_keys),
        "verified_items": verified,
        "evidence_confidence": round(confidence_sum / total, 2),
        "stale_keys": stale_keys,
    }


def actionable_gate(
    *,
    live_data: bool,
    overall_confidence: float,
    evidence_summary: dict[str, Any],
    strict_mode: bool,
    min_confidence: float = 0.60,
) -> dict[str, Any]:
    reasons: list[str] = []
    threshold = max(0.0, min(1.0, float(min_confidence)))
    if not live_data:
        reasons.append("demo/fallback data is never actionable")
    if overall_confidence < threshold:
        reasons.append(f"overall evidence confidence is below {round(threshold * 100)}%")
    if evidence_summary.get("evidence_items", 0) and evidence_summary.get("evidence_confidence", 0) < 0.55:
        reasons.append("source-level evidence confidence is below 55%")
    if evidence_summary.get("stale_items", 0) > 0:
        reasons.append("one or more critical evidence items are stale")
    if strict_mode and evidence_summary.get("verified_items", 0) < max(1, evidence_summary.get("evidence_items", 0) // 2):
        reasons.append("strict mode requires a majority of evidence items to have non-demo source provenance")
    return {"actionable": not reasons, "reasons": reasons}
