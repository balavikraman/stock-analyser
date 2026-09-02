from __future__ import annotations

from typing import Any


SECTOR_POLICY_TERMS = {
    "CAPITAL_GOODS": ("capital expenditure", "infrastructure", "railway", "roads"),
    "ENERGY": ("renewable", "solar", "power", "energy transition"),
    "CONSUMER": ("rural", "agriculture", "consumption"),
    "FINANCIALS": ("fiscal deficit", "borrowing", "banking"),
    "DEFENCE": ("defence", "defense"),
    "HEALTHCARE": ("health", "pharma"),
}


def classify_budget_policy(items: list[dict[str, Any]], sector: str | None) -> dict[str, Any]:
    """Classify only supplied, source-attributed official policy summaries."""
    normalized = (sector or "UNKNOWN").upper()
    terms = SECTOR_POLICY_TERMS.get(normalized, ())
    matches = [item for item in items if any(term in f"{item.get('title', '')} {item.get('summary', '')}".lower() for term in terms)]
    return {"sector": normalized, "available": bool(items), "relevant_items": matches[:5], "status": "RESEARCH_ONLY", "plain_meaning": "Policy may affect this sector, but company revenue exposure, valuation and market pricing still require review.", "absence_is_conclusive": False}
