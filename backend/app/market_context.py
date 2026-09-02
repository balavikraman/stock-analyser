from __future__ import annotations

from typing import Any

import pandas as pd


def _closes(rows: list[dict[str, Any]]) -> pd.Series:
    values = pd.to_numeric(pd.DataFrame(rows).get("close"), errors="coerce")
    return values.dropna().reset_index(drop=True) if values is not None else pd.Series(dtype=float)


def market_regime(benchmark_history: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify the broad market from a free benchmark series.

    This is a guardrail, not a forecast: unavailable benchmark data never becomes
    a bullish assumption.
    """
    close = _closes(benchmark_history)
    if len(close) < 200:
        return {"available": False, "regime": "UNKNOWN", "confidence": 0.0,
                "reason": "At least 200 benchmark sessions are required for the market-regime filter."}
    last = float(close.iloc[-1])
    sma50, sma200 = float(close.tail(50).mean()), float(close.tail(200).mean())
    return20 = (last / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else None
    if last < sma200 and sma50 < sma200:
        regime, reason = "RISK_OFF", "Benchmark is below its 200-session average and its 50-session trend is below the 200-session trend."
    elif last >= sma200 and sma50 >= sma200:
        regime, reason = "RISK_ON", "Benchmark price and medium-term trend are above the 200-session trend."
    else:
        regime, reason = "TRANSITION", "Benchmark trends disagree; broad-market conditions are mixed."
    return {"available": True, "regime": regime, "confidence": 0.8, "benchmark_price": round(last, 2),
            "sma50": round(sma50, 2), "sma200": round(sma200, 2),
            "return_20d_pct": round(return20, 2) if return20 is not None else None, "reason": reason}


def relative_strength(stock_history: list[dict[str, Any]], benchmark_history: list[dict[str, Any]], days: int = 60) -> dict[str, Any]:
    stock, benchmark = _closes(stock_history), _closes(benchmark_history)
    if len(stock) < days + 1 or len(benchmark) < days + 1:
        return {"available": False, "confidence": 0.0, "reason": f"At least {days + 1} sessions are required for relative strength."}
    stock_return = (float(stock.iloc[-1]) / float(stock.iloc[-days - 1]) - 1) * 100
    benchmark_return = (float(benchmark.iloc[-1]) / float(benchmark.iloc[-days - 1]) - 1) * 100
    excess = stock_return - benchmark_return
    label = "LEADING" if excess >= 5 else "LAGGING" if excess <= -5 else "IN_LINE"
    return {"available": True, "confidence": 0.7, "window_sessions": days,
            "stock_return_pct": round(stock_return, 2), "benchmark_return_pct": round(benchmark_return, 2),
            "excess_return_pct": round(excess, 2), "label": label}

