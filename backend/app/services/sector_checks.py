from __future__ import annotations

from typing import Any


def _pct(current: Any, previous: Any) -> float | None:
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)) or previous == 0:
        return None
    return (current / previous - 1) * 100


def assess_sector_risks(sector: str | None, annuals: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    """Small, explicit sector checks; missing sector data never becomes a score."""
    name = (sector or "").lower()
    latest, previous = (annuals[-1] if annuals else {}), (annuals[-2] if len(annuals) >= 2 else {})
    flags: list[dict[str, str]] = []
    profile = "GENERAL"
    if any(word in name for word in ("financial", "bank", "insurance")):
        profile = "FINANCIALS"
        if isinstance(metrics.get("pb"), (int, float)) and isinstance(metrics.get("roe"), (int, float)) and metrics["pb"] > 4 and metrics["roe"] < 12:
            flags.append({"severity": "medium", "message": "Financial stock trades at a high price-to-book ratio despite modest ROE; valuation needs deeper review."})
    elif any(word in name for word in ("energy", "oil", "gas", "utility", "power")):
        profile = "ENERGY_UTILITIES"
        if isinstance(metrics.get("debt_to_equity"), (int, float)) and metrics["debt_to_equity"] > 1:
            flags.append({"severity": "medium", "message": "Energy/utility leverage is elevated; assess rate, fuel-price and refinancing sensitivity."})
    elif any(word in name for word in ("consumer", "fmcg", "staples")):
        profile = "CONSUMER"
        margin_now = latest.get("operating_profit") / latest.get("revenue") if latest.get("revenue") else None
        margin_old = previous.get("operating_profit") / previous.get("revenue") if previous.get("revenue") else None
        if isinstance(margin_now, (int, float)) and isinstance(margin_old, (int, float)) and margin_now < margin_old - 0.03:
            flags.append({"severity": "medium", "message": "Consumer-company operating margin fell by more than three percentage points; pricing power or input costs need review."})
    elif any(word in name for word in ("industrial", "capital goods", "engineering", "manufacturing")):
        profile = "CAPITAL_GOODS"
        receivable_growth = _pct(latest.get("receivables"), previous.get("receivables"))
        revenue_growth = _pct(latest.get("revenue"), previous.get("revenue"))
        if isinstance(receivable_growth, float) and isinstance(revenue_growth, float) and receivable_growth > revenue_growth + 20:
            flags.append({"severity": "medium", "message": "Capital-goods receivables are growing much faster than revenue; project collections need review."})
    elif any(word in name for word in ("technology", "software", "it services")):
        profile = "IT_SERVICES"
        if isinstance(metrics.get("operating_margin"), (int, float)) and metrics["operating_margin"] < 12:
            flags.append({"severity": "medium", "message": "IT-services operating margin is low; verify utilization, pricing and delivery-cost pressure."})
    return {"profile": profile, "flags": flags, "available": bool(sector)}
