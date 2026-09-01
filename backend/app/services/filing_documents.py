from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from .official_facts import document_url
from .xbrl_parser import parse_xbrl_bytes


ALLOWED_HOSTS = {"nseindia.com", "www.nseindia.com", "archives.nseindia.com"}
MAX_DOWNLOAD_BYTES = 25_000_000


def _allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ALLOWED_HOSTS


def fetch_and_parse_xbrl(url: str, *, timeout: float = 15.0) -> dict[str, Any]:
    """Download one official NSE filing document and parse mapped XBRL facts."""
    if not _allowed_url(url):
        return {"ok": False, "facts": {}, "ambiguities": [], "error": "untrusted filing URL", "source_url": url}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
        "Accept": "application/xml,text/xml,application/xhtml+xml,text/html,application/zip,*/*",
        "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-application",
    }
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        return {"ok": False, "facts": {}, "ambiguities": [], "error": "filing document exceeds safe download size", "source_url": url}
                    chunks.append(chunk)
        parsed = parse_xbrl_bytes(b"".join(chunks))
        return {"ok": True, **parsed, "source_url": url, "download_bytes": total}
    except (httpx.HTTPError, ValueError) as exc:
        return {"ok": False, "facts": {}, "ambiguities": [], "error": f"{type(exc).__name__}: {exc}", "source_url": url}


def parse_latest_official_documents(bundle: dict[str, Any]) -> dict[str, Any]:
    """Parse only the latest financial-result and shareholding documents.

    This is opt-in because it performs extra network requests. Missing, blocked,
    PDF-only or ambiguous documents are reported rather than interpreted.
    """
    results: dict[str, Any] = {}
    merged_facts: dict[str, dict[str, Any]] = {}
    ambiguities: list[dict[str, Any]] = []

    for filing_type in ("financial_results", "shareholding"):
        rows = bundle.get(filing_type) or []
        if not rows:
            results[filing_type] = {"ok": False, "facts": {}, "ambiguities": [], "error": "no filing metadata available"}
            continue
        url = document_url(rows[0])
        if not url:
            results[filing_type] = {"ok": False, "facts": {}, "ambiguities": [], "error": "no document link in latest filing metadata"}
            continue
        parsed = fetch_and_parse_xbrl(url)
        results[filing_type] = parsed
        if not parsed.get("ok"):
            continue
        for key, fact in (parsed.get("facts") or {}).items():
            enriched = dict(fact)
            enriched["filing_type"] = filing_type
            enriched["source_url"] = url
            if key not in merged_facts:
                merged_facts[key] = enriched
            elif merged_facts[key].get("value") != enriched.get("value"):
                ambiguities.append({"metric": key, "reason": "different values across official filing documents", "candidates": [merged_facts[key], enriched]})
                merged_facts.pop(key, None)
        ambiguities.extend(parsed.get("ambiguities") or [])

    return {"documents": results, "facts": merged_facts, "ambiguities": ambiguities}
