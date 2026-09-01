from backend.app.scoring import combine_scores, fundamental_score, valuation_score


def test_fundamental_score_rewards_quality():
    metrics = {"roe": 28, "operating_margin": 24, "net_margin": 17, "debt_to_equity": 0.05, "interest_coverage": 12}
    annuals = [{"revenue": 100, "net_profit": 10, "fcf": 9}, {"revenue": 120, "net_profit": 13, "fcf": 12}, {"revenue": 150, "net_profit": 18, "fcf": 17}]
    result = fundamental_score(metrics, annuals, "Technology")
    assert result["score"] > 75
    assert result["confidence"] > 0.7


def test_missing_data_lowers_confidence():
    result = fundamental_score({"roe": 20}, [], "Technology")
    assert result["confidence"] < 0.4


def test_combine_uses_confidence():
    c = combine_scores({"fundamental": {"score": 90, "confidence": 1}, "valuation": {"score": 20, "confidence": 0.1}})
    assert c["score"] > 75
