from __future__ import annotations

from typing import Any


def summarize_holdings(holdings: list[dict[str, Any]]) -> dict[str, Any]:
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
    concentration = sum((r["weight_pct"] / 100) ** 2 for r in rows) * 100 if rows else 0
    return {"total_value": round(total, 2), "holdings": sorted(rows, key=lambda x: x["value"], reverse=True), "concentration_index": round(concentration, 2), "largest_position_pct": max((r["weight_pct"] for r in rows), default=0)}
