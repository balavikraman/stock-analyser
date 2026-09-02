from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _safe(v: Any) -> float | None:
    return round(float(v), 4) if v is not None and pd.notna(v) else None


def analyze_technicals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) < 30:
        return {"confidence": 0.0, "score": None, "reason": "Not enough price history"}
    df = pd.DataFrame(rows).copy()
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"])
    close = df["close"]
    for p in (20, 50, 100, 200):
        df[f"sma{p}"] = close.rolling(p).mean()
    df["rsi14"] = _rsi(close)
    ema12, ema26 = close.ewm(span=12, adjust=False).mean(), close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    tr = pd.concat([(df["high"] - df["low"]).abs(), (df["high"] - close.shift()).abs(), (df["low"] - close.shift()).abs()], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14).mean()
    df["vol20"] = df["volume"].rolling(20).mean()
    last = df.iloc[-1]
    price = float(last["close"])
    high_52 = float(close.tail(252).max())
    low_52 = float(close.tail(252).min())
    support20 = float(df["low"].tail(20).min())
    support60 = float(df["low"].tail(60).min())
    resistance20 = float(df["high"].tail(20).max())
    atr = float(last["atr14"]) if pd.notna(last["atr14"]) else None
    rsi = float(last["rsi14"]) if pd.notna(last["rsi14"]) else None
    avg_turnover = float((df["close"] * df["volume"]).tail(20).mean()) if df["volume"].tail(20).notna().any() else None
    volume_ratio = float(last["volume"] / last["vol20"]) if pd.notna(last["vol20"]) and last["vol20"] > 0 and pd.notna(last["volume"]) else None
    atr_pct = (atr / price * 100) if atr is not None and price else None

    points = available = 0.0
    for p, weight in ((20, 8), (50, 10), (100, 8), (200, 14)):
        ma = last[f"sma{p}"]
        if pd.notna(ma):
            available += weight
            points += weight if price >= ma else max(0, weight * (1 - min((ma - price) / ma, 0.15) / 0.15))
    if rsi is not None:
        available += 20
        if 40 <= rsi <= 65: points += 20
        elif 30 <= rsi < 40 or 65 < rsi <= 72: points += 14
        elif rsi < 30: points += 12
        else: points += 6
    available += 15
    drawdown = (price / high_52 - 1) * 100
    if -25 <= drawdown <= -5: points += 15
    elif drawdown < -25: points += 9
    else: points += 10
    available += 10
    if float(last["macd"]) >= float(last["macd_signal"]): points += 10
    available += 7
    if pd.notna(last["vol20"]) and last["vol20"] and last["volume"] >= last["vol20"]: points += 7
    else: points += 3
    score = round(points / available * 100, 1) if available else None
    confidence = min(1.0, len(df) / 252)
    liquidity = "UNKNOWN" if avg_turnover is None else "THIN" if avg_turnover < 1_000_000 else "ADEQUATE"
    return {"score": score, "confidence": round(confidence, 2), "price": price, "sma20": _safe(last["sma20"]), "sma50": _safe(last["sma50"]), "sma100": _safe(last["sma100"]), "sma200": _safe(last["sma200"]), "rsi14": _safe(last["rsi14"]), "macd": _safe(last["macd"]), "macd_signal": _safe(last["macd_signal"]), "atr14": atr, "atr_pct": _safe(atr_pct), "volume_ratio_20d": _safe(volume_ratio), "average_turnover_20d": _safe(avg_turnover), "liquidity": liquidity, "high_52w": high_52, "low_52w": low_52, "drawdown_from_52w_high_pct": round(drawdown, 2), "support_near": support20, "support_major": support60, "resistance_near": resistance20}
