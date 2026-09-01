from datetime import date, timedelta

from backend.app.technical import analyze_technicals


def test_technical_has_core_indicators():
    rows = []
    p = 100.0
    d = date(2025, 1, 1)
    for i in range(320):
        p += 0.18
        rows.append({"date": (d + timedelta(days=i)).isoformat(), "open": p-1, "high": p+2, "low": p-2, "close": p, "volume": 100000+i*100})
    r = analyze_technicals(rows)
    assert r["sma200"] is not None
    assert 0 <= r["score"] <= 100
    assert r["support_near"] <= r["resistance_near"]
