from backend.app.services.sebi_public import (
    classify_sebi_document,
    clean_query,
    discover_sebi_documents,
    extract_sebi_documents,
    is_official_sebi_document_url,
    matches_entity_query,
    public_listing_pages,
)


def test_clean_query_rejects_empty_url_and_excessive_input():
    assert clean_query(" Infosys Limited ") == "Infosys Limited"
    assert clean_query(" ") is None
    assert clean_query("https://example.com") is None
    assert clean_query("x" * 121) is None


def test_public_listing_pages_are_bounded_official_surfaces():
    pages = public_listing_pages()
    assert len(pages) == 7
    assert all(url.startswith("https://www.sebi.gov.in/sebiweb/home/HomeAction.do?") for _, url in pages)
    assert {section for section, _ in pages} >= {"member_order", "adjudication_order", "recovery_proceeding", "draft_offer_document"}


def test_only_official_https_sebi_document_links_are_trusted():
    assert is_official_sebi_document_url("https://www.sebi.gov.in/enforcement/orders/aug-2026/order_1.html")
    assert is_official_sebi_document_url("https://www.sebi.gov.in/sebi_data/attachdocs/aug-2026/order.pdf")
    assert is_official_sebi_document_url("https://www.sebi.gov.in/filings/public-issues/aug-2026/company_1.html")
    assert not is_official_sebi_document_url("http://www.sebi.gov.in/enforcement/orders/order.html")
    assert not is_official_sebi_document_url("https://sebi.gov.in.example.org/enforcement/orders/order.html")
    assert not is_official_sebi_document_url("https://www.sebi.gov.in/index.html")


def test_classifies_orders_recovery_and_offer_documents():
    assert classify_sebi_document("Adjudication Order in the matter of Example Limited", "https://www.sebi.gov.in/x") == "adjudication_order"
    assert classify_sebi_document("Interim Order in the matter of Example Limited", "https://www.sebi.gov.in/x") == "interim_order"
    assert classify_sebi_document("Recovery Certificate in the matter of Example Limited", "https://www.sebi.gov.in/x") == "recovery_proceeding"
    assert classify_sebi_document("Example Limited - DRHP", "https://www.sebi.gov.in/x") == "draft_offer_document"
    assert classify_sebi_document("Example Limited - Prospectus", "https://www.sebi.gov.in/x") == "final_offer_document"


def test_entity_matching_ignores_common_company_suffixes_but_requires_all_name_tokens():
    title = "Final Order in the matter of Infosys Limited"
    assert matches_entity_query(title, "Infosys Limited")
    assert matches_entity_query(title, "Infosys")
    assert not matches_entity_query(title, "Infosys Technologies")


def test_extract_documents_keeps_matching_official_rows_and_provenance():
    html = """
    <table>
      <tr><td>Aug 28, 2026</td><td><a title="Final Order in the matter of Infosys Limited"
        href="/enforcement/orders/aug-2026/infosys-order_1.html">Order</a></td></tr>
      <tr><td>Aug 27, 2026</td><td><a title="Final Order in the matter of Example Limited"
        href="/enforcement/orders/aug-2026/example-order_2.html">Order</a></td></tr>
      <tr><td>Aug 26, 2026</td><td><a title="Final Order in the matter of Infosys Limited"
        href="https://example.com/fake.pdf">Mirror</a></td></tr>
    </table>
    """
    page = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=2&smid=2&ssid=9"
    rows = extract_sebi_documents(html, page, "Infosys Limited", "member_order")
    assert len(rows) == 1
    assert rows[0].document_type == "final_order"
    assert rows[0].query == "Infosys Limited"
    assert rows[0].source_section == "member_order"
    assert rows[0].discovered_on == page
    assert rows[0].observed_at == "2026-08-28T00:00:00+00:00"


def test_invalid_query_fails_before_network_access():
    result = discover_sebi_documents("https://example.com")
    assert result["ok"] is False
    assert result["pages_scanned"] == []
    assert result["documents"] == []
    assert result["errors"]


def test_http_client_initialization_failure_is_reported_not_raised(monkeypatch):
    def unavailable_client(*args, **kwargs):
        raise ImportError("missing proxy transport")

    monkeypatch.setattr("backend.app.services.sebi_public.httpx.Client", unavailable_client)
    result = discover_sebi_documents("Infosys Limited")
    assert result["ok"] is False
    assert result["documents"] == []
    assert any("HTTP client unavailable: ImportError" in error for error in result["errors"])
    assert result["absence_is_conclusive"] is False
