from types import SimpleNamespace

from backend.app.portfolio import summarize_holdings
from backend.app.services.research_alerts import alert_status, build_research_alert


def test_portfolio_flags_overweight_position():
    result = summarize_holdings([
        {"tradingsymbol": "AAA", "quantity": 9, "last_price": 100, "average_price": 90},
        {"tradingsymbol": "BBB", "quantity": 1, "last_price": 100, "average_price": 100},
    ], max_position_pct=50, max_concentration_index=60)
    assert result["holdings"][0]["over_position_limit"] is True
    assert result["risk_warnings"]


def test_alert_preview_never_promotes_non_actionable_report():
    report = {"overall_confidence": 0.99, "data_quality": {"actionable": False}}
    assert build_research_alert(report, 0.7)["eligible"] is False


def test_alert_status_is_disabled_without_local_credentials():
    settings = SimpleNamespace(telegram_bot_token="", telegram_chat_id="", telegram_alerts_enabled=True, telegram_min_actionable_confidence=0.7)
    assert alert_status(settings)["enabled"] is False
