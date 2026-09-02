from __future__ import annotations

from typing import Any

import pandas as pd


def assess_market_breadth(histories: dict[str, list[dict[str, Any]]], minimum_symbols: int = 3) -> dict[str, Any]:
    """Breadth from the configured local watchlist, not a claim about all NSE stocks."""
    usable = []
    for symbol, rows in histories.items():
        close = pd.to_numeric(pd.DataFrame(rows).get("close"), errors="coerce").dropna() if rows else pd.Series(dtype=float)
        if len(close) < 51:
            continue
        last = float(close.iloc[-1]); sma50 = float(close.tail(50).mean())
        ret20 = (last / float(close.iloc[-21]) - 1) * 100
        usable.append({"symbol": symbol, "above_sma50": last >= sma50, "return_20d_pct": ret20})
    if len(usable) < minimum_symbols:
        return {"available": False, "universe": "configured watchlist", "symbols_used": len(usable), "reason": "Too few watchlist symbols had 51 sessions of usable price data."}
    pct_above = sum(row["above_sma50"] for row in usable) / len(usable) * 100
    positive = sum(row["return_20d_pct"] > 0 for row in usable) / len(usable) * 100
    state = "BROAD" if pct_above >= 65 and positive >= 60 else "NARROW" if pct_above < 40 or positive < 40 else "MIXED"
    return {"available": True, "universe": "configured watchlist", "symbols_used": len(usable), "pct_above_sma50": round(pct_above, 1), "pct_positive_20d": round(positive, 1), "state": state, "reason": "Watchlist breadth is a local proxy, not a full-market advance/decline dataset."}
