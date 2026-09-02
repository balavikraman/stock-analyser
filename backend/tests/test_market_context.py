from datetime import date, timedelta

from backend.app.market_context import market_regime, relative_strength
from backend.app.services.event_risk import assess_event_risk


def _rows(start: float, step: float, n: int = 260):
    day = date(2025, 1, 1)
    return [{"date": (day + timedelta(days=i)).isoformat(), "close": start + i * step} for i in range(n)]


def test_risk_on_market_and_leading_stock_are_identified():
    benchmark = _rows(100, 0.1)
    stock = _rows(100, 0.3)
    assert market_regime(benchmark)["regime"] == "RISK_ON"
    assert relative_strength(stock, benchmark)["label"] == "LEADING"


def test_risk_off_market_is_detected():
    assert market_regime(_rows(200, -0.3))["regime"] == "RISK_OFF"


def test_event_risk_requires_review_for_adverse_language():
    result = assess_event_risk([{"title": "Company faces regulatory investigation", "summary": ""}])
    assert result["level"] == "HIGH"
    assert result["automated_triage_only"] is True
