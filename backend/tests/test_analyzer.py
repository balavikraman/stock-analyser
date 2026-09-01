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
    assert "first_entry" in report.entry_plan
    assert report.data_quality["live_data"] is False
