from backend.app.market_breadth import assess_market_breadth


def test_broad_watchlist_breadth_is_detected():
    histories = {name: [{"close": 100 + i} for i in range(60)] for name in ("A", "B", "C")}
    result = assess_market_breadth(histories)
    assert result["state"] == "BROAD"
    assert result["symbols_used"] == 3


def test_insufficient_breadth_never_claims_market_state():
    result = assess_market_breadth({"A": [{"close": 100 + i} for i in range(60)]})
    assert result["available"] is False
