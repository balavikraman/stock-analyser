from __future__ import annotations

from typing import Any

POSITIVE = ("order win", "contract", "approval", "capacity expansion", "record", "upgrade", "partnership", "acquisition", "launch", "growth")
NEGATIVE = ("fraud", "default", "downgrade", "resignation", "investigation", "penalty", "recall", "loss", "decline", "lawsuit", "pledge")
STRUCTURAL = ("regulation", "ban", "tariff", "technology", "ai", "patent", "policy", "sanction", "geopolitical")


def classify_news(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in items:
        if item.get("classification") not in (None, "", "unclassified"):
            out.append(item); continue
        text = f"{item.get('title','')} {item.get('summary','')}".lower()
        pos = sum(k in text for k in POSITIVE); neg = sum(k in text for k in NEGATIVE); structural = any(k in text for k in STRUCTURAL)
        if pos > neg: cls, impact = ("structural_positive" if structural else "temporary_positive"), min(0.8, 0.2 + 0.15 * pos)
        elif neg > pos: cls, impact = ("structural_negative" if structural else "temporary_negative"), max(-0.8, -0.2 - 0.15 * neg)
        else: cls, impact = "noise_or_unclear", 0.0
        enriched = dict(item); enriched["classification"] = cls; enriched["impact"] = impact; out.append(enriched)
    return out


def research_score(news: list[dict[str, Any]]) -> dict[str, Any]:
    if not news:
        return {"score": None, "confidence": 0.0, "explanation": "No current news data"}
    impacts = [float(n.get("impact") or 0) for n in news]
    avg = sum(impacts) / max(1, len(impacts))
    score = max(0, min(100, 50 + avg * 55))
    conf = min(0.45, 0.18 + len(news) * 0.025)
    return {"score": round(score, 1), "confidence": round(conf, 2), "explanation": "Automated news triage only; deep research required for high confidence."}
