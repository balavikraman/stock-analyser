from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


ALIASES = {
    "revenue": ("revenue", "total income", "income from operations", "revenue from operations", "total revenue"),
    "net_profit": ("net profit", "profit after tax", "pat", "profit for the period", "profit for the year"),
    "eps": ("earnings per share", "basic eps", "eps"),
    "promoter_holding": ("promoter holding", "promoter and promoter group", "promoters"),
    "promoter_pledge": ("pledged", "encumbered", "promoter pledge"),
}


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip().replace(",", "").replace("₹", "").replace("%", "")
    if not text or text in {"-", "--", "na", "n/a"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group())
    return -number if negative else number


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def extract_structured_facts(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Extract only facts that are explicitly labelled in filing payloads.

    This intentionally does not guess column meaning or units. A fact without an
    explicit label/value pair stays unavailable until a document/XBRL parser can
    establish its context.
    """
    facts: dict[str, dict[str, Any]] = {}
    for row in rows:
        for node in _walk(row):
            label = None
            value = None
            for key in ("label", "particular", "particulars", "name", "description", "desc", "field"):
                if node.get(key) not in (None, ""):
                    label = node[key]
                    break
            for key in ("value", "amount", "current", "currentPeriod", "current_period", "percentage", "percent"):
                if node.get(key) not in (None, ""):
                    value = node[key]
                    break
            if label is None or value is None:
                continue
            normalized_label = _norm_key(label)
            parsed = _number(value)
            if parsed is None:
                continue
            for canonical, aliases in ALIASES.items():
                if any(alias in normalized_label for alias in aliases):
                    facts.setdefault(canonical, {
                        "value": parsed,
                        "label": str(label),
                        "raw_value": value,
                        "unit": node.get("unit") or node.get("units"),
                    })
    return facts


def compare_facts(provider_metrics: dict[str, Any], official_facts: dict[str, dict[str, Any]], tolerance_pct: float = 5.0) -> list[dict[str, Any]]:
    mappings = {
        "eps": "eps",
        "promoter_holding": "promoter_holding",
        "promoter_pledge": "promoter_pledge",
    }
    mismatches: list[dict[str, Any]] = []
    for fact_key, metric_key in mappings.items():
        official = official_facts.get(fact_key, {}).get("value")
        provider = provider_metrics.get(metric_key)
        if not isinstance(official, (int, float)) or not isinstance(provider, (int, float)):
            continue
        denominator = max(abs(float(official)), 1e-9)
        diff_pct = abs(float(provider) - float(official)) / denominator * 100
        if diff_pct > tolerance_pct:
            mismatches.append({
                "metric": metric_key,
                "provider_value": round(float(provider), 4),
                "official_value": round(float(official), 4),
                "difference_pct": round(diff_pct, 2),
                "severity": "high" if diff_pct >= 20 else "medium",
                "message": f"{metric_key} differs from official filing evidence by {diff_pct:.1f}%",
            })
    return mismatches


def source_key(symbol: str, filing_type: str, row: dict[str, Any]) -> str:
    explicit = next((row.get(k) for k in ("id", "seqId", "seq_id", "attachment", "fileName", "xbrlFile") if row.get(k)), None)
    if explicit:
        return str(explicit)[:255]
    raw = json.dumps(row, sort_keys=True, default=str).encode("utf-8")
    return f"{symbol}:{filing_type}:{hashlib.sha256(raw).hexdigest()[:32]}"


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt).replace(tzinfo=timezone.utc).replace(tzinfo=None)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def document_url(row: dict[str, Any]) -> str | None:
    value = next((row.get(k) for k in ("attchmntFile", "attachment", "fileUrl", "fileURL", "xbrlFile", "url") if row.get(k)), None)
    if not value:
        return None
    value = str(value)
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://www.nseindia.com/{value.lstrip('/')}"
