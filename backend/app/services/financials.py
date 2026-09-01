from __future__ import annotations

from typing import Any


def _pct(current: Any, previous: Any) -> float | None:
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)) or previous == 0:
        return None
    return round((current / previous - 1) * 100, 2)


def enrich_quarterlies(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [dict(r) for r in rows]
    for i, row in enumerate(out):
        prev = out[i - 1] if i >= 1 else {}
        yoy = out[i - 4] if i >= 4 else {}
        for metric in ("revenue", "operating_profit", "net_profit", "eps", "operating_margin"):
            if metric in row:
                row[f"{metric}_qoq_pct"] = _pct(row.get(metric), prev.get(metric))
                row[f"{metric}_yoy_pct"] = _pct(row.get(metric), yoy.get(metric))
    return out


def forensic_checks(annuals: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    flags = []
    score = 100.0
    latest = annuals[-1] if annuals else {}
    prev = annuals[-2] if len(annuals) >= 2 else {}
    net_profit = latest.get("net_profit"); cfo = latest.get("cfo")
    if isinstance(net_profit, (int, float)) and net_profit > 0:
        if isinstance(cfo, (int, float)):
            conversion = cfo / net_profit
            if conversion < 0.5:
                score -= 28; flags.append({"severity":"high","message":"Cash from operations is below half of reported profit; earnings quality needs investigation."})
            elif conversion < 0.8:
                score -= 12; flags.append({"severity":"medium","message":"Cash conversion trails accounting profit."})
        else:
            score -= 8; flags.append({"severity":"unknown","message":"Operating cash-flow data is missing, so earnings quality cannot be fully checked."})
    debt, prev_debt = latest.get("debt"), prev.get("debt")
    if isinstance(debt,(int,float)) and isinstance(prev_debt,(int,float)) and prev_debt > 0 and debt > prev_debt * 1.35:
        score -= 15; flags.append({"severity":"medium","message":"Debt increased more than 35% year over year."})
    rev_growth = _pct(latest.get("revenue"), prev.get("revenue")); profit_growth = _pct(latest.get("net_profit"), prev.get("net_profit"))
    if isinstance(rev_growth,float) and isinstance(profit_growth,float) and rev_growth > 5 and profit_growth < -10:
        score -= 12; flags.append({"severity":"medium","message":"Sales are growing while profit is falling sharply; margin quality is deteriorating."})
    de = metrics.get("debt_to_equity")
    if isinstance(de,(int,float)) and de > 1.5:
        score -= 20; flags.append({"severity":"high","message":"Debt-to-equity is high; balance-sheet risk deserves deeper review."})
    if not flags:
        flags.append({"severity":"info","message":"No automated cash-flow/debt red flag found in the available annual data."})
    return {"score":round(max(0,score),1),"flags":flags}
