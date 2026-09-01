from backend.app.services.filing_documents import fetch_and_parse_xbrl
from backend.app.services.xbrl_parser import parse_xbrl_bytes


def test_parse_latest_unambiguous_xbrl_facts():
    xml = b'''<?xml version="1.0" encoding="UTF-8"?>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:in="http://example.com/in">
      <xbrli:context id="C1"><xbrli:entity><xbrli:identifier scheme="x">ABC</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
      <in:RevenueFromOperations contextRef="C1" unitRef="INR" decimals="0">12345</in:RevenueFromOperations>
      <in:ProfitAfterTax contextRef="C1" unitRef="INR" decimals="0">1500</in:ProfitAfterTax>
      <in:BasicEarningsPerShare contextRef="C1" decimals="2">12.5</in:BasicEarningsPerShare>
    </xbrli:xbrl>'''
    parsed = parse_xbrl_bytes(xml)
    assert parsed["facts"]["revenue"]["value"] == 12345
    assert parsed["facts"]["net_profit"]["value"] == 1500
    assert parsed["facts"]["eps"]["value"] == 12.5
    assert parsed["ambiguities"] == []


def test_conflicting_latest_facts_are_not_silently_selected():
    xml = b'''<?xml version="1.0"?>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:in="http://example.com/in">
      <xbrli:context id="C1"><xbrli:entity><xbrli:identifier scheme="x">ABC</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:context id="C2"><xbrli:entity><xbrli:identifier scheme="x">ABC</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
      <in:BasicEarningsPerShare contextRef="C1">10</in:BasicEarningsPerShare>
      <in:BasicEarningsPerShare contextRef="C2">11</in:BasicEarningsPerShare>
    </xbrli:xbrl>'''
    parsed = parse_xbrl_bytes(xml)
    assert "eps" not in parsed["facts"]
    assert parsed["ambiguities"][0]["metric"] == "eps"


def test_untrusted_document_url_is_blocked_without_network():
    result = fetch_and_parse_xbrl("https://example.com/fake.xml")
    assert result["ok"] is False
    assert result["error"] == "untrusted filing URL"
