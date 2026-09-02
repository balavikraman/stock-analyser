from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


METALS = {"gold": {"symbol": "GC=F", "label": "Gold"}, "silver": {"symbol": "SI=F", "label": "Silver"}}


def analyse_metal(kind: str, history: list[dict[str, Any]], *, usd_inr: float | None = None) -> dict[str, Any]:
    """Build a conservative range view from verified daily closes only."""
    metal = METALS.get(kind.lower())
    if not metal:
        raise ValueError("metal must be gold or silver")
    closes = [float(row["close"]) for row in history if row.get("close")]
    if len(closes) < 21:
        return {"metal": metal["label"], "status": "BLOCKED — INSUFFICIENT VERIFIED DATA", "plain_meaning": "There are not enough verified daily prices to form a range.", "actionable": False, "missing": ["at least 21 verified daily closes"]}
    price, sma20 = closes[-1], sum(closes[-20:]) / 20
    change20 = (price / closes[-21] - 1) * 100
    bias = "UPWARD" if price > sma20 and change20 > 0 else "DOWNWARD" if price < sma20 and change20 < 0 else "MIXED"
    spread = max(abs(price - sma20), price * 0.015)
    return {"metal": metal["label"], "status": "RESEARCH ONLY", "plain_meaning": "This is a price-range scenario, not a guaranteed forecast or buy instruction.", "actionable": False, "as_of": datetime.now(timezone.utc).isoformat(), "price_usd": round(price, 2), "bias_1_2_weeks": bias, "support_usd": round(price - spread, 2), "resistance_usd": round(price + spread, 2), "change_20d_pct": round(change20, 2), "usd_inr": usd_inr, "drivers_required": ["USD/INR", "Fed expectations", "US dollar", "bond yields", "official macro events"], "probability": None, "probability_note": "Not calibrated until enough prospective metal outcomes exist."}
