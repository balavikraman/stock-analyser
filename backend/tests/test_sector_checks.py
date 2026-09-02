from backend.app.services.sector_checks import assess_sector_risks


def test_financial_sector_uses_price_to_book_and_roe_context():
    result = assess_sector_risks("Financial Services", [], {"pb": 5, "roe": 10})
    assert result["profile"] == "FINANCIALS"
    assert result["flags"]


def test_energy_sector_flags_elevated_leverage():
    result = assess_sector_risks("Energy", [], {"debt_to_equity": 1.2})
    assert result["profile"] == "ENERGY_UTILITIES"
    assert result["flags"]
