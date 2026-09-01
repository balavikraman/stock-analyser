from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

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
    """Download one official NSE filing document and parse mapped XBRL facts.

    Only HTTPS URLs on explicit NSE hosts are allowed. Download size is capped and
    parser errors are returned as structured failures instead of guessed facts.
    """
    if not _allowed_url(url):
        return {"ok": False, "facts": {}, "ambiguities": [], "error": "untrusted filing URL"}

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
                        return {"ok": False, "facts": {}, "ambiguities": [], "error": "filing document exceeds safe download size"}
                    chunks.append(chunk)
        parsed = parse_xbrl_bytes(b"".join(chunks))
        return {"ok": True, **parsed, "source_url": url, "download_bytes": total}
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "ok": False,
            "facts": {},
            "ambiguities": [],
            "error": f"{type(exc).__name__}: {exc}",
            "source_url": url,
        }
