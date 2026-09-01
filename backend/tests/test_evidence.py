from datetime import datetime, timedelta, timezone

from backend.app.evidence import actionable_gate, stale_status, summarize_evidence


def test_stale_evidence_is_detected():
    old = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    status = stale_status(old, 7)
    assert status["is_stale"] is True
    assert status["age_days"] >= 19


def test_demo_data_is_never_actionable():
    gate = actionable_gate(
        live_data=False,
        overall_confidence=0.95,
        evidence_summary={"evidence_items": 5, "verified_items": 0, "evidence_confidence": 0.95, "stale_items": 0},
        strict_mode=False,
        min_confidence=0.60,
    )
    assert gate["actionable"] is False
    assert any("demo" in reason for reason in gate["reasons"])


def test_low_confidence_blocks_action():
    gate = actionable_gate(
        live_data=True,
        overall_confidence=0.49,
        evidence_summary={"evidence_items": 5, "verified_items": 5, "evidence_confidence": 0.80, "stale_items": 0},
        strict_mode=True,
        min_confidence=0.60,
    )
    assert gate["actionable"] is False


def test_evidence_summary_penalizes_stale_source():
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    evidence = {
        "price": {"source": "provider", "source_type": "aggregator", "observed_at": old, "confidence": 0.8, "stale_after_days": 7},
        "financials": {"source": "provider", "source_type": "aggregator", "fetched_at": datetime.now(timezone.utc).isoformat(), "confidence": 0.7, "stale_after_days": None},
    }
    summary = summarize_evidence(evidence)
    assert summary["stale_items"] == 1
    assert "price" in summary["stale_keys"]
    assert summary["evidence_confidence"] < 0.7
