"""A bounded next-trading-day scenario from the latest completed daily candle.

This intentionally reports a range and invalidation level, never a promised
tomorrow close or a calibrated probability.
"""
from __future__ import annotations

from typing import Any


def build_tomorrow_outlook(
    price: float | None,
    technical: dict[str, Any],
    market: dict[str, Any],
    breadth: dict[str, Any],
    relative_strength: dict[str, Any],
    actionable: bool,
) -> dict[str, Any]:
    if not isinstance(price, (int, float)) or price <= 0:
        return {
            "status": "UNAVAILABLE",
            "plain_meaning": "A next-session range needs a verified latest closing price.",
            "actionable": False,
            "probability": None,
        }

    atr = technical.get("atr14")
    if not isinstance(atr, (int, float)) or atr <= 0:
        return {
            "status": "UNAVAILABLE",
            "plain_meaning": "A next-session range needs enough recent daily price history to measure normal movement.",
            "actionable": False,
            "probability": None,
        }

    rsi = technical.get("rsi14")
    above_sma50 = isinstance(technical.get("sma50"), (int, float)) and price >= technical["sma50"]
    leading = relative_strength.get("label") == "LEADING"
    supportive_market = market.get("regime") == "RISK_ON" and breadth.get("state") == "BROAD"
    adverse_market = market.get("regime") == "RISK_OFF" or breadth.get("state") == "NARROW"
    if adverse_market or (isinstance(rsi, (int, float)) and rsi >= 72):
        bias = "CAUTIOUS / DOWNSIDE RISK"
        meaning = "The next session may be volatile or weak. Waiting is safer than chasing a trade."
    elif supportive_market and above_sma50 and leading and (not isinstance(rsi, (int, float)) or rsi < 68):
        bias = "CONSTRUCTIVE, BUT NOT GUARANTEED"
        meaning = "Trend and market participation support a positive scenario, but an overnight gap can still invalidate it."
    else:
        bias = "NEUTRAL / WAIT FOR CONFIRMATION"
        meaning = "Signals are mixed. Treat this as a range to observe, not a direction to trade."

    support = technical.get("support_near")
    resistance = technical.get("resistance_near")
    return {
        "status": "NEXT TRADING DAY SCENARIO",
        "as_of_price": round(float(price), 2),
        "bias": bias,
        "expected_low": round(float(price) - float(atr), 2),
        "expected_high": round(float(price) + float(atr), 2),
        "support": round(float(support), 2) if isinstance(support, (int, float)) else None,
        "resistance": round(float(resistance), 2) if isinstance(resistance, (int, float)) else None,
        "invalidation": "A close below nearby support weakens this scenario.",
        "plain_meaning": meaning,
        "actionable": bool(actionable),
        "probability": None,
        "probability_note": "No probability is shown until enough comparable prospective outcomes have been measured.",
    }
