from backend.app.services.official_facts import compare_facts, extract_structured_facts, source_key


def test_extracts_only_explicit_labelled_facts():
    rows = [{"data": [{"particulars": "Basic EPS", "value": "18.40"}, {"particulars": "Profit after tax", "amount": "1,250.5"}]}]
    facts = extract_structured_facts(rows)
    assert facts["eps"]["value"] == 18.4
    assert facts["net_profit"]["value"] == 1250.5


def test_unlabelled_numbers_are_not_guessed():
    assert extract_structured_facts([{"value": "999", "foo": "bar"}]) == {}


def test_material_provider_official_mismatch_is_flagged():
    mismatches = compare_facts({"eps": 25.0}, {"eps": {"value": 20.0}})
    assert len(mismatches) == 1
    assert mismatches[0]["difference_pct"] == 25.0
    assert mismatches[0]["severity"] == "high"


def test_small_difference_is_tolerated():
    assert compare_facts({"eps": 20.5}, {"eps": {"value": 20.0}}) == []


def test_source_key_is_stable_for_same_row():
    row = {"symbol": "INFY", "period": "2026-06-30", "value": 1}
    assert source_key("INFY", "financial_results", row) == source_key("INFY", "financial_results", row)
