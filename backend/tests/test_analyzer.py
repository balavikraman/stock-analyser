import os

os.environ["DATA_PROVIDER"] = "demo"

from backend.app.config import get_settings
get_settings.cache_clear()
from backend.app.services.analyzer import StockAnalyzer


def test_demo_report_complete():
    report = StockAnalyzer().analyze("DEMO.NS")
    assert report.overall_score is not None
    assert report.overall_confidence > 0.5
    assert len(report.annuals) >= 5
    assert report.entry_plan["actionable"] is False
    assert report.entry_plan["status"] == "BLOCKED — EVIDENCE REVIEW REQUIRED"
    assert "first_entry" not in report.entry_plan
    assert "demo/fallback data is never actionable" in report.entry_plan["block_reasons"]
    assert report.data_quality["live_data"] is False


def test_forensic_score_is_exposed_for_decision_review():
    report = StockAnalyzer().analyze("DEMO.NS")
    assert "forensic_score" in report.data_quality
