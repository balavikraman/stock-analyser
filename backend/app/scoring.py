from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Callable


@dataclass
class MetricRule:
    key: str
    weight: float
    scorer: Callable[[float], float]
    good_text: str


def clamp(v: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, v))


def higher(v: float, bad: float, good: float) -> float:
    return 50 if good == bad else clamp((v - bad) / (good - bad) * 100)


def lower(v: float, good: float, bad: float) -> float:
    return 50 if bad == good else clamp((bad - v) / (bad - good) * 100)


def _valid(v: Any) -> bool:
    return isinstance(v, (int, float)) and isfinite(float(v))


def compute_growth(annuals: list[dict[str, Any]]) -> dict[str, Any]:
    def cagr(key: str) -> float | None:
        vals = [float(r[key]) for r in annuals if _valid(r.get(key)) and float(r[key]) > 0]
        if len(vals) < 2:
            return None
        years = len(vals) - 1
        return round(((vals[-1] / vals[0]) ** (1 / years) - 1) * 100, 2)
    out = {"revenue_cagr": cagr("revenue"), "profit_cagr": cagr("net_profit")}
    latest = annuals[-1] if annuals else {}
    if _valid(latest.get("fcf")) and _valid(latest.get("net_profit")) and latest.get("net_profit"):
        out["fcf_conversion"] = round(float(latest["fcf"]) / float(latest["net_profit"]), 2)
    else:
        out["fcf_conversion"] = None
    return out


def fundamental_score(metrics: dict[str, Any], annuals: list[dict[str, Any]], sector: str | None = None) -> dict[str, Any]:
    sector_l = (sector or "").lower()
    is_financial = any(k in sector_l for k in ("financial", "bank", "insurance"))
    rules = [
        MetricRule("roe", 16, lambda v: higher(v, 8, 24), "High shareholder capital efficiency"),
        MetricRule("operating_margin", 10, lambda v: higher(v, 8, 24), "Healthy operating profitability"),
        MetricRule("net_margin", 8, lambda v: higher(v, 4, 16), "Healthy net profitability"),
    ]
    if not is_financial:
        rules += [
            MetricRule("debt_to_equity", 14, lambda v: lower(v, 0.15, 1.5), "Manageable leverage"),
            MetricRule("interest_coverage", 10, lambda v: higher(v, 1.5, 8), "Comfortable interest coverage"),
        ]
    growth = compute_growth(annuals)
    for k, v in growth.items():
        metrics.setdefault(k, v)
    rules += [
        MetricRule("revenue_cagr", 13, lambda v: higher(v, 3, 15), "Consistent sales growth"),
        MetricRule("profit_cagr", 14, lambda v: higher(v, 2, 18), "Consistent profit growth"),
        MetricRule("fcf_conversion", 15, lambda v: higher(v, 0.45, 1.0), "Accounting profit converts to cash"),
    ]
    earned = 0.0
    total = sum(r.weight for r in rules)
    used = []
    for r in rules:
        v = metrics.get(r.key)
        if _valid(v):
            s = r.scorer(float(v))
            earned += s * r.weight
            used.append({"metric": r.key, "value": v, "score": round(s, 1), "weight": r.weight})
    available_weight = sum(x["weight"] for x in used)
    score = earned / available_weight if available_weight else None
    confidence = available_weight / total if total else 0
    return {"score": round(score, 1) if score is not None else None, "confidence": round(confidence, 2), "details": used, "growth": growth}


def valuation_score(metrics: dict[str, Any], sector: str | None = None) -> dict[str, Any]:
    sector_l = (sector or "").lower()
    is_financial = any(k in sector_l for k in ("financial", "bank", "insurance"))
    if is_financial:
        checks = [("pb", 45, lambda v: lower(v, 1.2, 5.0)), ("pe", 25, lambda v: lower(v, 12, 35)), ("dividend_yield", 10, lambda v: higher(v, 0, 4)), ("roe", 20, lambda v: higher(v, 8, 20))]
    else:
        checks = [("pe", 35, lambda v: lower(v, 14, 45)), ("pb", 15, lambda v: lower(v, 1.5, 8)), ("peg", 20, lambda v: lower(v, 0.8, 3.0)), ("dividend_yield", 10, lambda v: higher(v, 0, 4)), ("fcf_yield", 20, lambda v: higher(v, 1, 6))]
    earned = available = total = 0.0
    details = []
    for key, weight, fn in checks:
        total += weight
        v = metrics.get(key)
        if _valid(v) and float(v) >= 0:
            s = fn(float(v)); earned += s * weight; available += weight
            details.append({"metric": key, "value": v, "score": round(s, 1), "weight": weight})
    return {"score": round(earned / available, 1) if available else None, "confidence": round(available / total, 2), "details": details}


def governance_score(metrics: dict[str, Any]) -> dict[str, Any]:
    pledge = metrics.get("promoter_pledge")
    if _valid(pledge):
        s = lower(float(pledge), 0, 50)
        return {"score": round(s, 1), "confidence": 0.35, "details": [{"metric": "promoter_pledge", "value": pledge, "score": round(s, 1)}]}
    return {"score": None, "confidence": 0.0, "details": []}


def combine_scores(components: dict[str, dict[str, Any]]) -> dict[str, Any]:
    weights = {"fundamental": 0.34, "valuation": 0.22, "technical": 0.16, "governance": 0.10, "research": 0.18}
    numerator = denominator = conf_num = 0.0
    for key, weight in weights.items():
        comp = components.get(key, {})
        score, conf = comp.get("score"), float(comp.get("confidence") or 0)
        if _valid(score) and conf > 0:
            effective = weight * conf
            numerator += float(score) * effective
            denominator += effective
            conf_num += weight * conf
    overall = numerator / denominator if denominator else None
    confidence = conf_num / sum(weights.values())
    return {"score": round(overall, 1) if overall is not None else None, "confidence": round(confidence, 2)}
