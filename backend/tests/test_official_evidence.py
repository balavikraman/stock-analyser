from backend.app.providers.nse_official import NSEOfficialEvidenceProvider
from backend.app.services.official_evidence import clean_nse_symbol, official_evidence_summary


def test_clean_nse_symbol():
    assert clean_nse_symbol(" infy.ns ") == "INFY"
    assert clean_nse_symbol("HDFCBANK") == "HDFCBANK"


def test_nse_date_parser_is_fail_closed():
    assert NSEOfficialEvidenceProvider._iso_date("01-Sep-2026") is not None
    assert NSEOfficialEvidenceProvider._iso_date("not-a-date") is None
    assert NSEOfficialEvidenceProvider._iso_date(None) is None


def test_official_evidence_summary_does_not_require_network():
    bundle = {
        "source": "National Stock Exchange of India",
        "evidence": {
            "nse_latest_financial_result": {"confidence": 0.95},
            "nse_latest_shareholding": {"confidence": 0.95},
        },
        "announcements": [{"subject": "Board meeting"}],
        "financial_results": [{"period": "Q1"}],
        "shareholding": [{"period": "Q1"}],
        "errors": [],
        "cache": {"hit": False},
    }
    summary = official_evidence_summary(bundle)
    assert summary["available"] is True
    assert summary["official_items"] == 2
    assert summary["latest_financial_result_found"] is True
    assert summary["latest_shareholding_found"] is True
    assert summary["latest_announcement_found"] is False
