from datetime import datetime, timezone

from backend.app.services.official_events import assess_official_events


def test_recent_official_governance_disclosure_blocks_for_review():
    now = datetime.now(timezone.utc).strftime("%d-%b-%Y %H:%M:%S")
    bundle = {"available": True, "source": "NSE", "announcements": [{"subject": "Resignation of director", "broadcastDateTime": now}]}
    result = assess_official_events(bundle, review_days=7)
    assert result["review_required"] is True
    assert result["recent_events"][0]["category"] == "GOVERNANCE"


def test_old_or_unclassified_filing_does_not_claim_clearance():
    bundle = {"available": True, "announcements": [{"subject": "Routine update", "broadcastDate": "01-Jan-2020"}]}
    result = assess_official_events(bundle)
    assert result["review_required"] is False
    assert "not conclusive" in result["reason"]
