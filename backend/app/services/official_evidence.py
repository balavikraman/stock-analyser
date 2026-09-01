from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from ..config import get_settings
from ..providers.nse_official import NSEOfficialEvidenceProvider


_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}
_CACHE_LOCK = Lock()


def clean_nse_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(".NS", "")


def _empty_bundle(symbol: str, reason: str | None = None) -> dict[str, Any]:
    return {
        "symbol": clean_nse_symbol(symbol),
        "announcements": [],
        "financial_results": [],
        "shareholding": [],
        "evidence": {},
        "errors": [reason] if reason else [],
        "source": "National Stock Exchange of India",
        "available": False,
    }


def fetch_official_evidence(symbol: str, *, force: bool = False) -> dict[str, Any]:
    """Fetch exchange filing metadata with a small in-process cache.

    The cache protects NSE from repeated requests when the dashboard refreshes or the
    scanner analyzes the same symbol more than once. Provider failures are returned as
    explicit errors; an empty response is never interpreted as proof that no filing exists.
    """
    settings = get_settings()
    if not settings.official_evidence_enabled:
        return _empty_bundle(symbol, "Official evidence provider disabled by configuration.")

    key = clean_nse_symbol(symbol)
    now = datetime.now(timezone.utc)
    ttl = timedelta(minutes=max(1, settings.official_evidence_cache_minutes))

    if not force:
        with _CACHE_LOCK:
            cached = _CACHE.get(key)
            if cached and now - cached[0] < ttl:
                payload = deepcopy(cached[1])
                payload["cache"] = {"hit": True, "cached_at": cached[0].isoformat()}
                return payload

    try:
        payload = NSEOfficialEvidenceProvider().fetch_bundle(key)
    except Exception as exc:  # provider must fail closed even on unexpected parser changes
        payload = _empty_bundle(key, f"NSE official evidence unavailable: {type(exc).__name__}")

    payload["available"] = bool(payload.get("evidence"))
    payload["cache"] = {"hit": False, "cached_at": now.isoformat()}
    with _CACHE_LOCK:
        _CACHE[key] = (now, deepcopy(payload))
    return payload


def official_evidence_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    evidence = bundle.get("evidence") or {}
    return {
        "available": bool(evidence),
        "source": bundle.get("source") or "National Stock Exchange of India",
        "official_items": len(evidence),
        "latest_financial_result_found": "nse_latest_financial_result" in evidence,
        "latest_shareholding_found": "nse_latest_shareholding" in evidence,
        "latest_announcement_found": "nse_latest_announcement" in evidence,
        "announcement_count": len(bundle.get("announcements") or []),
        "financial_result_count": len(bundle.get("financial_results") or []),
        "shareholding_count": len(bundle.get("shareholding") or []),
        "errors": list(bundle.get("errors") or []),
        "cache": bundle.get("cache") or {},
    }
