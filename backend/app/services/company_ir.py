from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


IR_PAGE_KEYWORDS = (
    "investor", "investors", "investor-relations", "investorrelations", "financials",
    "reports", "results", "annual-report", "quarterly-results", "earnings",
)

DOCUMENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("annual_report", ("annual report", "annual-report", "integrated report", "annualreport")),
    ("quarterly_result", ("quarterly result", "quarter results", "financial result", "results for the quarter", "q1 result", "q2 result", "q3 result", "q4 result")),
    ("investor_presentation", ("investor presentation", "earnings presentation", "analyst presentation", "presentation")),
    ("earnings_release", ("earnings release", "press release", "results press release", "financial release")),
    ("transcript", ("transcript", "earnings call", "conference call", "analyst call")),
    ("guidance", ("guidance", "outlook")),
)

MAX_PAGES = 8
MAX_DOCUMENTS = 80
MAX_HTML_BYTES = 2_000_000


@dataclass(frozen=True)
class IRDocument:
    document_type: str
    title: str
    url: str
    discovered_on: str
    issuer_host: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_company_url(url: str | None) -> str | None:
    if not url:
        return None
    text = url.strip()
    if not text:
        return None
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return parsed._replace(fragment="").geturl()


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def same_issuer_domain(base_url: str, candidate_url: str) -> bool:
    base = _host(base_url)
    candidate = _host(candidate_url)
    if not base or not candidate:
        return False
    return candidate == base or candidate.endswith("." + base) or base.endswith("." + candidate)


def classify_document(label: str, url: str) -> str | None:
    haystack = f"{label} {url}".lower().replace("_", " ")
    for document_type, keywords in DOCUMENT_RULES:
        if any(keyword in haystack for keyword in keywords):
            return document_type
    return None


def extract_ir_links(html: str, page_url: str, issuer_url: str) -> tuple[list[str], list[IRDocument]]:
    soup = BeautifulSoup(html, "html.parser")
    pages: list[str] = []
    documents: list[IRDocument] = []
    seen_pages: set[str] = set()
    seen_docs: set[str] = set()
    issuer_host = _host(issuer_url)

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(page_url, href).split("#", 1)[0]
        if not same_issuer_domain(issuer_url, absolute):
            continue
        label = " ".join(anchor.stripped_strings).strip() or absolute.rsplit("/", 1)[-1]
        lowered = f"{label} {absolute}".lower()
        doc_type = classify_document(label, absolute)
        is_document = absolute.lower().split("?", 1)[0].endswith((".pdf", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx"))

        if doc_type and (is_document or "download" in lowered or "report" in lowered or "result" in lowered or "presentation" in lowered or "transcript" in lowered):
            if absolute not in seen_docs:
                seen_docs.add(absolute)
                documents.append(IRDocument(doc_type, label[:300], absolute, page_url, issuer_host))
            continue

        if any(keyword in lowered for keyword in IR_PAGE_KEYWORDS) and absolute not in seen_pages:
            seen_pages.add(absolute)
            pages.append(absolute)

    return pages[:MAX_PAGES], documents[:MAX_DOCUMENTS]


def _fetch_html(client: httpx.Client, url: str) -> str | None:
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "html" not in content_type:
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


def discover_ir_documents(issuer_url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    normalized = normalize_company_url(issuer_url)
    if not normalized:
        return {"ok": False, "issuer_url": issuer_url, "documents": [], "pages_scanned": [], "errors": ["invalid issuer website"]}

    headers = {
        "User-Agent": "StockAnalyzerResearch/0.5 (+local personal research)",
        "Accept": "text/html,application/xhtml+xml",
    }
    queue = [normalized]
    scanned: list[str] = []
    documents: dict[str, IRDocument] = {}
    errors: list[str] = []

    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        while queue and len(scanned) < MAX_PAGES:
            url = queue.pop(0)
            if url in scanned or not same_issuer_domain(normalized, url):
                continue
            html = _fetch_html(client, url)
            scanned.append(url)
            if html is None:
                errors.append(f"IR page unavailable or non-HTML: {url}")
                continue
            pages, docs = extract_ir_links(html, url, normalized)
            for doc in docs:
                documents.setdefault(doc.url, doc)
            for page in pages:
                if page not in scanned and page not in queue and len(queue) + len(scanned) < MAX_PAGES:
                    queue.append(page)

    return {
        "ok": bool(documents),
        "issuer_url": normalized,
        "issuer_host": _host(normalized),
        "documents": [doc.to_dict() for doc in list(documents.values())[:MAX_DOCUMENTS]],
        "pages_scanned": scanned,
        "errors": errors,
        "source_type": "company_filing",
        "authority": "official",
    }
