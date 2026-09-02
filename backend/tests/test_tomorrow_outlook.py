from backend.app.services.tomorrow_outlook import build_tomorrow_outlook


def test_outlook_is_range_not_probability_or_exact_price():
    outlook = build_tomorrow_outlook(
        100, {"atr14": 3, "sma50": 95, "rsi14": 55, "support_near": 96, "resistance_near": 104},
        {"regime": "RISK_ON"}, {"state": "BROAD"}, {"label": "LEADING"}, True,
    )
    assert outlook["expected_low"] == 97
    assert outlook["expected_high"] == 103
    assert outlook["probability"] is None
    assert outlook["actionable"] is True


def test_outlook_stays_cautious_when_breadth_is_narrow():
    outlook = build_tomorrow_outlook(100, {"atr14": 3}, {"regime": "RISK_ON"}, {"state": "NARROW"}, {}, False)
    assert outlook["bias"] == "CAUTIOUS / DOWNSIDE RISK"
    assert outlook["actionable"] is False
