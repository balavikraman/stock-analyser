from backend.app.services.source_registry import registry_payload, source_registry_summary, sources_for_sector


def test_registry_has_active_official_and_secondary_sources():
    summary = source_registry_summary()
    assert summary["total"] >= 10
    assert summary["active"] >= 2
    assert summary["official"] >= 8
    assert summary["free_public_strategy"] is True


def test_bank_sector_includes_rbi_and_core_sources():
    keys = [row["key"] for row in sources_for_sector("Banks and financial services")]
    assert "nse_filings" in keys
    assert "company_ir" in keys
    assert "bse_public" in keys
    assert "rbi" in keys


def test_telecom_sector_includes_trai():
    keys = [row["key"] for row in sources_for_sector("Telecommunications")]
    assert "trai" in keys


def test_active_only_hides_planned_adapters():
    payload = registry_payload("telecom", include_planned=False)
    assert all(row["adapter_status"] == "active" for row in payload["sources"])
    assert "bse_public" in {row["key"] for row in payload["sources"]}
    assert "sebi_filings" in {row["key"] for row in payload["sources"]}
