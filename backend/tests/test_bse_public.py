from backend.app.services.bse_public import (
    classify_filing,
    clean_scrip_code,
    extract_bse_filings,
    is_official_bse_url,
    public_filing_pages,
)


def test_clean_scrip_code_requires_exactly_six_digits():
    assert clean_scrip_code(" 500209 ") == "500209"
    assert clean_scrip_code("INFY") is None
    assert clean_scrip_code("50020") is None
    assert clean_scrip_code("500209.NS") is None


def test_public_pages_are_bounded_and_company_filtered():
    pages = public_filing_pages("500209")
    assert len(pages) == 5
    assert all(url.startswith("https://www.bseindia.com/corporates/") for _, url in pages)
    assert all("500209" in url for _, url in pages)


def test_only_official_https_bse_filing_links_are_trusted():
    assert is_official_bse_url("https://www.bseindia.com/xml-data/corpfiling/AttachLive/id.pdf")
    assert is_official_bse_url("https://beta.bseindia.com/corporates/anndet_new.aspx?newsid=id")
    assert not is_official_bse_url("http://www.bseindia.com/xml-data/corpfiling/AttachLive/id.pdf")
    assert not is_official_bse_url("https://bseindia.com.example.org/xml-data/corpfiling/id.pdf")
    assert not is_official_bse_url("https://www.bseindia.com/markets/marketinfo.html")


def test_classifies_supported_bse_filing_types():
    assert classify_filing("Unaudited Financial Results", "https://www.bseindia.com/x") == "financial_result"
    assert classify_filing("Shareholding Pattern", "https://www.bseindia.com/x") == "shareholding"
    assert classify_filing("Final Dividend and Record Date", "https://www.bseindia.com/x") == "corporate_action"
    assert classify_filing("Postal Ballot Voting Results", "https://www.bseindia.com/x") == "governance"


def test_extract_filings_keeps_matching_scrip_and_official_provenance():
    html = """
    <table>
      <tr><td>500209</td><td>Infosys Limited</td><td>01/08/2026</td>
        <td><a href="/xml-data/corpfiling/AttachLive/infy-results.pdf">Unaudited Financial Results</a></td></tr>
      <tr><td>500209</td><td>Infosys Limited</td><td>31/07/2026</td>
        <td><a href="https://www.bseindia.com/corporates/anndet_new.aspx?newsid=abc">Regulation 30 Disclosure</a></td></tr>
      <tr><td>500112</td><td>State Bank of India</td><td>01/08/2026</td>
        <td><a href="/xml-data/corpfiling/AttachLive/sbi-results.pdf">Financial Results</a></td></tr>
      <tr><td>500209</td><td>Infosys Limited</td>
        <td><a href="https://example.com/fake.pdf">Financial Results mirror</a></td></tr>
    </table>
    """
    page = "https://www.bseindia.com/corporates/ann?dur=A&scrip=500209"
    rows = extract_bse_filings(html, page, "500209", "announcement")
    assert len(rows) == 2
    assert {row.filing_type for row in rows} == {"financial_result", "announcement"}
    assert all(row.scrip_code == "500209" for row in rows)
    assert all(row.discovered_on == page for row in rows)
    assert rows[0].observed_at == "2026-08-01T00:00:00+00:00"
    assert all("example.com" not in row.url and "sbi-results" not in row.url for row in rows)


def test_extract_filings_rejects_context_without_requested_code():
    html = '<a href="/xml-data/corpfiling/AttachLive/unscoped.pdf">Financial Results</a>'
    assert extract_bse_filings(html, "https://www.bseindia.com/corporates/ann", "500209") == []
