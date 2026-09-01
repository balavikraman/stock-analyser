from __future__ import annotations

from typing import Any

from .official_evidence import official_evidence_summary
from .official_facts import compare_facts, extract_structured_facts


def assess_official_bundle(bundle: dict[str, Any], provider_metrics: dict[str, Any]) -> dict[str, Any]:
    """Normalize official filing metadata and compare explicit facts with provider data."""
    rows = (bundle.get("financial_results") or []) + (bundle.get("shareholding") or [])
    facts = extract_structured_facts(rows)
    mismatches = compare_facts(provider_metrics, facts)
    summary = official_evidence_summary(bundle)
    high = [item for item in mismatches if item.get("severity") == "high"]
    medium = [item for item in mismatches if item.get("severity") == "medium"]
    return {
        "summary": summary,
        "facts": facts,
        "mismatches": mismatches,
        "high_mismatch_count": len(high),
        "medium_mismatch_count": len(medium),
        "verified": bool(summary.get("available")) and not high,
    }


def official_action_blocks(assessment: dict[str, Any], *, required: bool) -> list[str]:
    reasons: list[str] = []
    summary = assessment.get("summary") or {}
    if required and not summary.get("available"):
        reasons.append("required official NSE filing evidence is unavailable")
    if assessment.get("high_mismatch_count", 0):
        reasons.append("high-severity mismatch exists between normalized data and official filing evidence")
    return reasons
