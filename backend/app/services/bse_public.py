from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


BSE_BASE_URL = "https://www.bseindia.com"
MAX_PAGES = 5
MAX_HTML_BYTES = 2_000_000
MAX_FILINGS = 100

FILING_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("financial_result", ("financial result", "quarterly result", "audited result", "unaudited result", "xbrl result")),
    ("shareholding", ("shareholding", "shareholding pattern", "promoter holding", "pledge", "encumbrance")),
    ("corporate_action", ("dividend", "bonus", "stock split", "record date", "rights issue", "buyback", "corporate action")),
    ("governance", ("corporate governance", "voting result", "annual general meeting", "postal ballot", "board meeting")),
    ("announcement", ("announcement", "regulation 30", "press release", "investor presentation", "transcript", "disclosure")),
)


@dataclass(frozen=True)
class BSEFiling:
    filing_type: str
    title: str
    url: str
    discovered_on: str
    scrip_code: str
    security_name: str | None = None
    observed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clean_scrip_code(value: str | int) -> str | None:
    text = str(value).strip()
    return text if re.fullmatch(r"\d{6}", text) else None


def public_filing_pages(scrip_code: str | int) -> list[tuple[str, str]]:
    code = clean_scrip_code(scrip_code)
    if not code:
        return []
    pages = (
        ("announcement", "/corporates/ann", {"dur": "A", "scrip": code}),
        ("financial_result", "/corporates/Comp_ResultsNew", {"expandable": "0", "scripcode": code}),
        ("shareholding", "/corporates/Sharehold_Searchnew", {"expandable": "6", "flag": "7", "scripcode": code}),
        ("corporate_action", "/corporates/corporates-act", {"scripcode": code}),
        ("governance", "/corporates/Corpgovernane", {"scripcode": code}),
    )
    return [(filing_type, f"{BSE_BASE_URL}{path}?{urlencode(params)}") for filing_type, path, params in pages]


def is_official_bse_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "bseindia.com" or host.endswith(".bseindia.com")):
        return False
    path = parsed.path.lower()
    return path.startswith(("/xml-data/corpfiling/", "/corporates/download/", "/corporates/anndet_new"))


def classify_filing(label: str, url: str, default: str | None = None) -> str | None:
    haystack = re.sub(r"[_-]+", " ", f"{label} {url}".lower())
    for filing_type, keywords in FILING_RULES:
        if any(keyword in haystack for keyword in keywords):
            return filing_type
    return default if default in {rule[0] for rule in FILING_RULES} else None


def _observed_at(text: str) -> str | None:
    patterns = (
        (r"\b\d{2}/\d{2}/\d{4}\b", "%d/%m/%Y"),
        (r"\b\d{2}-\d{2}-\d{4}\b", "%d-%m-%Y"),
        (r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b", "%d %B %Y"),
        (r"\b\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\b", "%d %b %Y"),
    )
    for pattern, fmt in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            return datetime.strptime(match.group(), fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def _security_name(row_text: str, scrip_code: str) -> str | None:
    remainder = re.sub(rf"^.*?\b{re.escape(scrip_code)}\b", "", row_text, count=1).strip(" |-:")
    if not remainder:
        return None
    remainder = re.split(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b|\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b", remainder, maxsplit=1)[0]
    return remainder.strip(" |-")[:200] or None


def extract_bse_filings(html: str, page_url: str, scrip_code: str | int, default_type: str | None = None) -> list[BSEFiling]:
    code = clean_scrip_code(scrip_code)
    if not code:
        return []
    soup = BeautifulSoup(html, "html.parser")
    filings: list[BSEFiling] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(page_url, str(anchor.get("href") or "").strip()).split("#", 1)[0]
        if absolute in seen or not is_official_bse_url(absolute):
            continue
        container = anchor.find_parent("tr") or anchor.find_parent(("li", "article", "div"))
        context = " ".join(container.stripped_strings) if container else " ".join(anchor.stripped_strings)
        context = re.sub(r"\s+", " ", context).strip()
        codes = set(re.findall(r"\b\d{6}\b", context))
        if code not in codes:
            continue
        label = " ".join(anchor.stripped_strings).strip() or context
        filing_type = classify_filing(f"{label} {context}", absolute, default_type)
        if not filing_type:
            continue
        seen.add(absolute)
        filings.append(BSEFiling(
            filing_type=filing_type,
            title=(label or context)[:300],
            url=absolute,
            discovered_on=page_url,
            scrip_code=code,
            security_name=_security_name(context, code),
            observed_at=_observed_at(context),
        ))
        if len(filings) >= MAX_FILINGS:
            break
    return filings


def _fetch_html(client: httpx.Client, url: str) -> str | None:
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            if "html" not in response.headers.get("content-type", "").lower():
                return None
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_HTML_BYTES:
                    return None
                chunks.append(chunk)
        return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
    except (httpx.HTTPError, UnicodeError):
        return None


def discover_bse_filings(scrip_code: str | int, *, timeout: float = 12.0) -> dict[str, Any]:
    code = clean_scrip_code(scrip_code)
    if not code:
        return {"ok": False, "scrip_code": str(scrip_code), "filings": [], "pages_scanned": [], "errors": ["BSE scrip code must contain exactly six digits"]}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": BSE_BASE_URL + "/",
    }
    pages = public_filing_pages(code)[:MAX_PAGES]
    scanned: list[str] = []
    errors: list[str] = []
    filings: dict[str, BSEFiling] = {}

    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        try:
            client.get(BSE_BASE_URL + "/")
        except httpx.HTTPError:
            pass
        for filing_type, page_url in pages:
            html = _fetch_html(client, page_url)
            scanned.append(page_url)
            if html is None:
                errors.append(f"BSE {filing_type} page unavailable or non-HTML")
                continue
            for filing in extract_bse_filings(html, page_url, code, filing_type):
                filings.setdefault(filing.url, filing)

    return {
        "ok": bool(filings),
        "scrip_code": code,
        "filings": [row.to_dict() for row in list(filings.values())[:MAX_FILINGS]],
        "pages_scanned": scanned,
        "errors": errors,
        "source": "BSE Limited",
        "source_type": "exchange_filing",
        "authority": "official",
        "discovery_only": True,
    }
