from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


SEBI_BASE_URL = "https://www.sebi.gov.in"
MAX_PAGES = 7
MAX_HTML_BYTES = 2_000_000
MAX_DOCUMENTS = 100
MAX_WORKERS = 3

LISTING_SECTIONS: tuple[tuple[str, int, int, int], ...] = (
    ("member_order", 2, 9, 2),
    ("settlement_order", 2, 9, 3),
    ("adjudication_order", 2, 9, 6),
    ("recovery_proceeding", 2, 50, 0),
    ("draft_offer_document", 3, 15, 10),
    ("red_herring_document", 3, 15, 11),
    ("final_offer_document", 3, 15, 12),
)

DOCUMENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("recovery_proceeding", ("recovery certificate", "recovery proceeding", "release order", "remittance order", "attachment of bank")),
    ("takeover_order", ("takeover", "substantial acquisition", "sast regulation", "sast regulations")),
    ("adjudication_order", ("adjudication order", "adjudication proceedings")),
    ("settlement_order", ("settlement order", "settlement application")),
    ("interim_order", ("interim order", "ex-parte order", "ex parte order")),
    ("final_order", ("final order", "revocation order", "exemption order", "confirmatory order")),
    ("draft_offer_document", ("drhp", "udrhp", "draft offer document", "draft abridged prospectus")),
    ("red_herring_document", ("rhp", "red herring prospectus")),
    ("final_offer_document", ("prospectus", "final offer document")),
    ("regulatory_order", ("order", "directions", "corrigendum")),
)

COMPANY_SUFFIXES = {
    "co", "company", "corp", "corporation", "inc", "india", "limited", "ltd", "plc", "private", "pvt",
}


@dataclass(frozen=True)
class SEBIDocument:
    document_type: str
    title: str
    url: str
    discovered_on: str
    source_section: str
    query: str
    observed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clean_query(value: str | None) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) < 2 or len(text) > 120 or "://" in text:
        return None
    return text


def public_listing_pages() -> list[tuple[str, str]]:
    pages: list[tuple[str, str]] = []
    for section, sid, ssid, smid in LISTING_SECTIONS[:MAX_PAGES]:
        params = urlencode({"doListing": "yes", "sid": sid, "smid": smid, "ssid": ssid})
        pages.append((section, f"{SEBI_BASE_URL}/sebiweb/home/HomeAction.do?{params}"))
    return pages


def is_official_sebi_document_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "sebi.gov.in" or host.endswith(".sebi.gov.in")):
        return False
    path = parsed.path.lower()
    return path.startswith(("/enforcement/", "/filings/", "/sebi_data/attachdocs/", "/sebi_data/commondocs/"))


def classify_sebi_document(label: str, url: str, default: str | None = None) -> str | None:
    haystack = re.sub(r"[_-]+", " ", f"{label} {url}".lower())
    for document_type, keywords in DOCUMENT_RULES:
        if any(keyword in haystack for keyword in keywords):
            return document_type
    return default if default in {section[0] for section in LISTING_SECTIONS} else None


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def matches_entity_query(title: str, query: str) -> bool:
    raw_query_tokens = _tokens(query)
    query_tokens = raw_query_tokens - COMPANY_SUFFIXES
    if not query_tokens:
        query_tokens = raw_query_tokens
    return bool(query_tokens) and query_tokens.issubset(_tokens(title))


def _observed_at(text: str) -> str | None:
    patterns = (
        (r"\b[A-Za-z]{3}\s+\d{1,2},\s+\d{4}\b", "%b %d, %Y"),
        (r"\b\d{2}/\d{2}/\d{4}\b", "%d/%m/%Y"),
        (r"\b\d{2}-\d{2}-\d{4}\b", "%d-%m-%Y"),
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


def extract_sebi_documents(html: str, page_url: str, query: str, default_type: str | None = None) -> list[SEBIDocument]:
    cleaned_query = clean_query(query)
    if not cleaned_query:
        return []
    soup = BeautifulSoup(html, "html.parser")
    documents: list[SEBIDocument] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(page_url, str(anchor.get("href") or "").strip()).split("#", 1)[0]
        if absolute in seen or not is_official_sebi_document_url(absolute):
            continue
        title = str(anchor.get("title") or " ".join(anchor.stripped_strings)).strip()
        title = re.sub(r"\s+", " ", title)
        if not title or not matches_entity_query(title, cleaned_query):
            continue
        document_type = classify_sebi_document(title, absolute, default_type)
        if not document_type:
            continue
        container = anchor.find_parent("tr") or anchor.find_parent(("li", "article", "div"))
        context = " ".join(container.stripped_strings) if container else title
        seen.add(absolute)
        documents.append(SEBIDocument(
            document_type=document_type,
            title=title[:500],
            url=absolute,
            discovered_on=page_url,
            source_section=default_type or document_type,
            query=cleaned_query,
            observed_at=_observed_at(context),
        ))
        if len(documents) >= MAX_DOCUMENTS:
            break
    return documents


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


def discover_sebi_documents(query: str, *, timeout: float = 12.0) -> dict[str, Any]:
    cleaned_query = clean_query(query)
    if not cleaned_query:
        return {"ok": False, "query": query, "documents": [], "pages_scanned": [], "errors": ["SEBI entity query must contain 2 to 120 characters and must not be a URL"]}

    headers = {
        "User-Agent": "StockAnalyzerResearch/0.5 (+local personal research)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    pages = public_listing_pages()
    documents: dict[str, SEBIDocument] = {}
    errors: list[str] = []

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(pages))) as executor:
                fetched = list(executor.map(lambda item: _fetch_html(client, item[1]), pages))
    except (httpx.HTTPError, ImportError, OSError, ValueError) as exc:
        fetched = [None] * len(pages)
        errors.append(f"SEBI HTTP client unavailable: {type(exc).__name__}")
    for (section, page_url), html in zip(pages, fetched):
        if html is None:
            errors.append(f"SEBI {section} page unavailable or non-HTML")
            continue
        for document in extract_sebi_documents(html, page_url, cleaned_query, section):
            documents.setdefault(document.url, document)

    rows = [row.to_dict() for row in list(documents.values())[:MAX_DOCUMENTS]]
    return {
        "ok": bool(rows),
        "query": cleaned_query,
        "documents": rows,
        "pages_scanned": [url for _, url in pages],
        "errors": errors,
        "source": "Securities and Exchange Board of India",
        "source_type": "regulator_filing",
        "authority": "official",
        "discovery_only": True,
        "complete_history": False,
        "absence_is_conclusive": False,
        "scope_note": "Latest records rendered on the selected public SEBI listing pages; no match is not proof that no historical SEBI record exists.",
    }
