from backend.app.services.official_validation import assess_official_bundle, official_action_blocks


def test_high_official_mismatch_blocks_action():
    bundle = {
        "source": "National Stock Exchange of India",
        "errors": [],
        "evidence": {"nse_latest_financial_result": {"source": "NSE"}},
        "financial_results": [{"label": "Basic EPS", "value": "10.00"}],
        "shareholding": [],
        "announcements": [],
    }
    assessment = assess_official_bundle(bundle, {"eps": 15.0})
    assert assessment["high_mismatch_count"] == 1
    assert official_action_blocks(assessment, required=False)


def test_required_official_evidence_blocks_when_unavailable():
    bundle = {"source": "National Stock Exchange of India", "errors": ["unavailable"], "evidence": {}, "financial_results": [], "shareholding": [], "announcements": []}
    assessment = assess_official_bundle(bundle, {"eps": 10.0})
    reasons = official_action_blocks(assessment, required=True)
    assert "required official NSE filing evidence is unavailable" in reasons
