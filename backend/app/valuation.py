from __future__ import annotations

from typing import Any


def build_scenarios(metrics: dict[str, Any], growth: dict[str, Any]) -> dict[str, Any]:
    price, eps = metrics.get("price"), metrics.get("eps")
    if not isinstance(eps, (int, float)) or eps <= 0:
        return {"method": "unavailable", "reason": "Positive EPS unavailable; fair value intentionally not guessed."}
    g = growth.get("profit_cagr") if isinstance(growth.get("profit_cagr"), (int, float)) else 8.0
    g = max(-5.0, min(float(g), 25.0))
    cases = {
        "bear": {"growth": max(-5, g * 0.35), "pe": max(8, min(18, 10 + g * 0.25))},
        "base": {"growth": max(0, g * 0.65), "pe": max(10, min(28, 12 + g * 0.45))},
        "bull": {"growth": max(2, g * 0.9), "pe": max(12, min(38, 14 + g * 0.65))},
    }
    horizon = 3
    for case in cases.values():
        future_eps = eps * ((1 + case["growth"] / 100) ** horizon)
        case["future_eps"] = round(future_eps, 2)
        case["value_3y"] = round(future_eps * case["pe"], 2)
        if isinstance(price, (int, float)) and price > 0:
            case["implied_cagr"] = round(((case["value_3y"] / price) ** (1 / horizon) - 1) * 100, 2)
    return {"method": "3-year EPS growth × exit P/E; heuristic, not a guaranteed target", "horizon_years": horizon, **cases}


def build_entry_plan(price: float | None, technicals: dict[str, Any], scenarios: dict[str, Any], overall_confidence: float) -> dict[str, Any]:
    if not isinstance(price, (int, float)) or price <= 0:
        return {"status": "WAIT", "reason": "Current price unavailable"}
    support = technicals.get("support_near") or price * 0.96
    major = technicals.get("support_major") or price * 0.90
    atr = technicals.get("atr14") or price * 0.025
    base_value = scenarios.get("base", {}).get("value_3y") if isinstance(scenarios.get("base"), dict) else None
    first_low = max(0.01, min(price, support) - 0.35 * atr)
    first_high = min(price * 1.01, support + 0.35 * atr)
    accum_low = max(0.01, min(major, support - 1.4 * atr))
    accum_high = max(accum_low, min(support - 0.25 * atr, price * 0.97))
    do_not_chase = max(price * 1.08, technicals.get("resistance_near") or price * 1.08)
    partial = base_value if isinstance(base_value, (int, float)) and base_value > price else max(price * 1.25, do_not_chase * 1.10)
    status = "ACCUMULATE GRADUALLY" if overall_confidence >= 0.7 else "WATCH / SMALL STARTER ONLY"
    return {"status": status, "first_entry": [round(first_low, 2), round(first_high, 2)], "accumulation": [round(accum_low, 2), round(accum_high, 2)], "do_not_chase_above": round(do_not_chase, 2), "partial_profit_review_from": round(partial, 2), "staging": [25, 25, 25, 25], "rule": "Average down only when the fundamental thesis remains intact; a falling price alone is never a buy signal."}
