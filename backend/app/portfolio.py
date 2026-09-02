from __future__ import annotations

from typing import Any


def summarize_holdings(holdings: list[dict[str, Any]], max_position_pct: float = 15.0, max_concentration_index: float = 25.0) -> dict[str, Any]:
    total = 0.0
    rows = []
    for h in holdings:
        qty = float(h.get("quantity") or 0) + float(h.get("t1_quantity") or 0)
        price = float(h.get("last_price") or 0)
        avg = float(h.get("average_price") or 0)
        value = qty * price
        invested = qty * avg
        pnl = value - invested
        total += value
        rows.append({"symbol": h.get("tradingsymbol"), "quantity": qty, "average_price": avg, "last_price": price, "value": round(value, 2), "pnl": round(pnl, 2), "pnl_pct": round((pnl / invested * 100), 2) if invested else None})
    for r in rows:
        r["weight_pct"] = round(r["value"] / total * 100, 2) if total else 0
        r["over_position_limit"] = r["weight_pct"] > max_position_pct
    concentration = sum((r["weight_pct"] / 100) ** 2 for r in rows) * 100 if rows else 0
    largest = max((r["weight_pct"] for r in rows), default=0)
    warnings = []
    if largest > max_position_pct:
        warnings.append(f"Largest holding is {largest:.2f}% of the portfolio, above the {max_position_pct:.2f}% concentration guardrail.")
    if concentration > max_concentration_index:
        warnings.append(f"Portfolio concentration index is {concentration:.2f}, above the {max_concentration_index:.2f} guardrail.")
    return {"total_value": round(total, 2), "holdings": sorted(rows, key=lambda x: x["value"], reverse=True), "concentration_index": round(concentration, 2), "largest_position_pct": largest, "risk_limits": {"max_position_pct": max_position_pct, "max_concentration_index": max_concentration_index}, "risk_warnings": warnings}
