from backend.app.services.company_ir import (
    classify_document,
    extract_ir_links,
    normalize_company_url,
    same_issuer_domain,
)


def test_normalize_company_url_adds_https():
    assert normalize_company_url("infosys.com") == "https://infosys.com"


def test_same_issuer_domain_accepts_subdomain_and_rejects_external():
    assert same_issuer_domain("https://infosys.com", "https://www.infosys.com/investors") is True
    assert same_issuer_domain("https://infosys.com", "https://investors.infosys.com/reports") is True
    assert same_issuer_domain("https://infosys.com", "https://example.com/report.pdf") is False


def test_classifies_supported_document_types():
    assert classify_document("Annual Report 2025-26", "https://issuer.com/ar.pdf") == "annual_report"
    assert classify_document("Q4 Quarterly Results", "https://issuer.com/q4.pdf") == "quarterly_result"
    assert classify_document("Investor Presentation", "https://issuer.com/presentation.pdf") == "investor_presentation"
    assert classify_document("Earnings Call Transcript", "https://issuer.com/transcript.pdf") == "transcript"


def test_extract_ir_links_keeps_issuer_docs_and_drops_external_links():
    html = """
    <html><body>
      <a href="/investors/reports">Investor Relations Reports</a>
      <a href="/investors/annual-report-2026.pdf">Annual Report 2025-26</a>
      <a href="/investors/q4-results.pdf">Quarterly Results Q4</a>
      <a href="/investors/q4-transcript.pdf">Earnings Call Transcript</a>
      <a href="https://example.com/fake-annual-report.pdf">Annual Report mirror</a>
      <a href="/careers">Careers</a>
    </body></html>
    """
    pages, docs = extract_ir_links(html, "https://www.issuer.com/investors", "https://issuer.com")
    assert "https://www.issuer.com/investors/reports" in pages
    assert {d.document_type for d in docs} == {"annual_report", "quarterly_result", "transcript"}
    assert all("example.com" not in d.url for d in docs)
