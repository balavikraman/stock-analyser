from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..providers.nse_official import NSEOfficialEvidenceProvider


EVENT_TERMS = {
    "RESULTS": ("financial results", "earnings", "quarterly results", "board meeting"),
    "CORPORATE_ACTION": ("dividend", "buyback", "split", "bonus", "rights issue"),
    "GOVERNANCE": ("resignation", "auditor", "statutory auditor", "independent director", "key managerial", "fraud", "investigation", "default", "pledge", "penalty"),
}


def assess_official_events(bundle: dict[str, Any], review_days: int = 7) -> dict[str, Any]:
    """Classify official exchange filing metadata without claiming an event date.

    Exchange announcements can be filed after an event is scheduled. Therefore this
    is a review gate for recent material disclosures, not an event calendar promise.
    """
    now = datetime.now(timezone.utc)
    events = []
    for row in bundle.get("announcements") or []:
        subject = str(NSEOfficialEvidenceProvider._pick(row, "subject", "desc", "announcement") or "")
        text = subject.lower()
        category = next((name for name, terms in EVENT_TERMS.items() if any(term in text for term in terms)), None)
        if not category:
            continue
        observed = NSEOfficialEvidenceProvider._iso_date(NSEOfficialEvidenceProvider._pick(row, "broadcastDateTime", "broadcastDate", "an_dt", "date"))
        age_days = None
        if observed:
            age_days = max(0, (now - datetime.fromisoformat(observed)).days)
        events.append({"category": category, "subject": subject, "observed_at": observed, "age_days": age_days, "official_source": bundle.get("source")})
    recent = [e for e in events if e["age_days"] is not None and e["age_days"] <= review_days]
    governance = [e for e in recent if e["category"] == "GOVERNANCE"]
    return {"available": bool(bundle.get("available")), "review_window_days": review_days, "events": events[:10], "recent_events": recent[:5], "review_required": bool(governance), "reason": "Recent official governance-risk disclosure requires manual review before acting." if governance else "No recent official governance-risk disclosure was classified; absence is not conclusive."}
