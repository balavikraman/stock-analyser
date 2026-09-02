from backend.app.services.financials import enrich_quarterlies, forensic_checks


def test_quarterly_qoq_and_yoy():
    rows = [{"revenue":100,"net_profit":10},{"revenue":110,"net_profit":12},{"revenue":120,"net_profit":13},{"revenue":130,"net_profit":14},{"revenue":150,"net_profit":18}]
    out = enrich_quarterlies(rows)
    assert out[-1]["revenue_qoq_pct"] == 15.38
    assert out[-1]["revenue_yoy_pct"] == 50.0


def test_forensic_low_cash_conversion_flags():
    r = forensic_checks([{"revenue":100,"net_profit":20,"cfo":5,"debt":10}], {})
    assert r["score"] < 80
    assert any(x["severity"] == "high" for x in r["flags"])


def test_forensic_receivables_growth_flags_working_capital_risk():
    r = forensic_checks([
        {"revenue": 100, "net_profit": 12, "cfo": 12, "receivables": 10},
        {"revenue": 110, "net_profit": 14, "cfo": 13, "receivables": 18},
    ], {})
    assert any("Receivables" in x["message"] for x in r["flags"])


def test_financial_sector_does_not_apply_industrial_debt_rules():
    r = forensic_checks([{"revenue": 100, "net_profit": 10, "cfo": 1, "debt": 100}], {"debt_to_equity": 3}, "Financial Services")
    assert r["score"] == 100


def test_share_dilution_is_flagged():
    r = forensic_checks([
        {"revenue": 100, "net_profit": 10, "cfo": 10, "shares_outstanding": 100},
        {"revenue": 110, "net_profit": 11, "cfo": 11, "shares_outstanding": 110},
    ], {})
    assert any("dilution" in x["message"].lower() for x in r["flags"])
