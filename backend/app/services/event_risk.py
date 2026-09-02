from __future__ import annotations

from typing import Any


HIGH_RISK_TERMS = ("fraud", "default", "investigation", "penalty", "recall", "resignation", "lawsuit", "pledge")
CAUTION_TERMS = ("results", "earnings", "board meeting", "dividend", "buyback", "split", "rights issue", "merger", "acquisition")


def assess_event_risk(news: list[dict[str, Any]]) -> dict[str, Any]:
    """Conservative title/summary triage; it never claims an event is verified."""
    high, caution = [], []
    for item in news:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        title = item.get("title") or "Untitled item"
        if any(term in text for term in HIGH_RISK_TERMS):
            high.append(title)
        elif any(term in text for term in CAUTION_TERMS):
            caution.append(title)
    if high:
        level, reason = "HIGH", "Potentially material adverse event language was found in current news and needs official-source verification."
    elif caution:
        level, reason = "CAUTION", "Potential results or corporate-action language was found; verify dates and filings before acting."
    else:
        level, reason = "NONE", "No event-risk keywords were found in the available news feed; this is not proof that no event exists."
    return {"level": level, "reason": reason, "high_risk_items": high[:5], "caution_items": caution[:5], "automated_triage_only": True}
