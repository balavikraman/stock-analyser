from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    name: str
    source_type: str
    authority: str
    access: str
    adapter_status: str
    base_url: str
    data_types: tuple[str, ...]
    sectors: tuple[str, ...] = ("all",)
    typical_freshness: str = "event-driven"
    priority: int = 50
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# Registry values describe source strategy, not a claim that every source already has
# a production adapter. `adapter_status` must remain explicit so the UI/API never
# confuses a planned source with an active ingestion path.
SOURCES: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        key="nse_filings",
        name="NSE Corporate Filings",
        source_type="exchange",
        authority="official",
        access="public-web",
        adapter_status="active",
        base_url="https://www.nseindia.com/companies-listing/corporate-filings-financial-results",
        data_types=("financial_results", "announcements", "shareholding", "xbrl", "corporate_actions"),
        priority=100,
        notes="Primary exchange evidence. Endpoint/document failures must fail closed.",
    ),
    SourceDefinition(
        key="company_ir",
        name="Company Investor Relations",
        source_type="company_filing",
        authority="official",
        access="public-web",
        adapter_status="planned",
        base_url="company-specific",
        data_types=("annual_reports", "quarterly_results", "presentations", "earnings_releases", "guidance", "transcripts"),
        priority=98,
        notes="Company-specific adapter/discovery required; prefer issuer-hosted documents.",
    ),
    SourceDefinition(
        key="bse_public",
        name="BSE Public Corporate Filings",
        source_type="exchange",
        authority="official",
        access="public-web",
        adapter_status="planned",
        base_url="https://www.bseindia.com/",
        data_types=("financial_results", "announcements", "shareholding", "corporate_actions", "governance"),
        priority=96,
        notes="Use public filing documents/pages only; do not depend on undocumented paid-feed APIs.",
    ),
    SourceDefinition(
        key="sebi_filings",
        name="SEBI Filings and Orders",
        source_type="regulator",
        authority="official",
        access="public-web",
        adapter_status="planned",
        base_url="https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3",
        data_types=("offer_documents", "takeovers", "regulatory_filings", "orders", "enforcement"),
        priority=95,
        notes="Useful for governance, capital raises, acquisitions and regulatory risk.",
    ),
    SourceDefinition(
        key="rbi",
        name="Reserve Bank of India / DBIE",
        source_type="regulator",
        authority="official",
        access="public-web",
        adapter_status="planned",
        base_url="https://data.rbi.org.in/",
        data_types=("rates", "banking_system", "credit", "deposits", "fx", "inflation", "liquidity", "macro"),
        sectors=("banks", "nbfc", "financials", "all"),
        typical_freshness="daily/monthly/quarterly",
        priority=94,
    ),
    SourceDefinition(
        key="trai",
        name="TRAI Performance Indicators",
        source_type="regulator",
        authority="official",
        access="public-web",
        adapter_status="planned",
        base_url="https://www.trai.gov.in/release-publication/reports/performance-indicators-reports",
        data_types=("subscribers", "market_size", "usage", "arpu_context", "qos", "broadband"),
        sectors=("telecom",),
        typical_freshness="monthly/quarterly",
        priority=92,
    ),
    SourceDefinition(
        key="ppac",
        name="Petroleum Planning & Analysis Cell",
        source_type="government",
        authority="official",
        access="public-web",
        adapter_status="planned",
        base_url="https://ppac.gov.in/",
        data_types=("natural_gas_consumption", "petroleum_consumption", "prices", "imports", "sector_demand"),
        sectors=("oil_gas", "energy", "gas_utilities"),
        typical_freshness="monthly",
        priority=92,
    ),
    SourceDefinition(
        key="cea",
        name="Central Electricity Authority",
        source_type="government",
        authority="official",
        access="public-web",
        adapter_status="planned",
        base_url="https://cea.nic.in/",
        data_types=("installed_capacity", "generation", "power_demand", "plant_load_factor", "transmission"),
        sectors=("power", "utilities", "renewables"),
        typical_freshness="daily/monthly",
        priority=92,
    ),
    SourceDefinition(
        key="steel_ministry",
        name="Ministry of Steel",
        source_type="government",
        authority="official",
        access="public-web",
        adapter_status="planned",
        base_url="https://steel.gov.in/",
        data_types=("steel_production", "consumption", "prices", "imports", "exports", "industry_reports"),
        sectors=("steel", "metals"),
        typical_freshness="monthly",
        priority=90,
    ),
    SourceDefinition(
        key="coal_ministry",
        name="Ministry of Coal",
        source_type="government",
        authority="official",
        access="public-web",
        adapter_status="planned",
        base_url="https://coal.gov.in/",
        data_types=("coal_production", "dispatch", "imports", "sector_supply"),
        sectors=("coal", "power", "energy"),
        typical_freshness="monthly",
        priority=90,
    ),
    SourceDefinition(
        key="yfinance",
        name="Yahoo Finance via yfinance",
        source_type="aggregator",
        authority="secondary",
        access="public-library",
        adapter_status="active",
        base_url="https://finance.yahoo.com/",
        data_types=("prices", "price_history", "snapshot_ratios", "normalized_financials", "news_links"),
        priority=60,
        notes="Convenience/secondary source. Important facts should be cross-checked against official evidence.",
    ),
)


def _sector_tokens(sector: str | None) -> set[str]:
    text = (sector or "").lower().replace("&", " ").replace("/", " ").replace("-", " ")
    tokens = {part.strip() for part in text.split() if part.strip()}
    aliases = {
        "bank": "banks",
        "banking": "banks",
        "financial": "financials",
        "telecommunications": "telecom",
        "telecommunication": "telecom",
        "oil": "oil_gas",
        "gas": "oil_gas",
        "electric": "power",
        "electricity": "power",
        "metal": "metals",
    }
    tokens.update(aliases[token] for token in list(tokens) if token in aliases)
    return tokens


def sources_for_sector(sector: str | None, *, include_planned: bool = True) -> list[dict]:
    tokens = _sector_tokens(sector)
    selected: list[SourceDefinition] = []
    for source in SOURCES:
        if not include_planned and source.adapter_status != "active":
            continue
        if "all" in source.sectors or not tokens or tokens.intersection(source.sectors):
            selected.append(source)
    selected.sort(key=lambda item: item.priority, reverse=True)
    return [source.to_dict() for source in selected]


def source_registry_summary(sources: Iterable[SourceDefinition] = SOURCES) -> dict:
    rows = list(sources)
    return {
        "total": len(rows),
        "active": sum(1 for source in rows if source.adapter_status == "active"),
        "planned": sum(1 for source in rows if source.adapter_status == "planned"),
        "official": sum(1 for source in rows if source.authority == "official"),
        "free_public_strategy": True,
        "policy": "official/regulator/company sources first; secondary aggregators for convenience and cross-checking; missing evidence is never guessed",
    }


def registry_payload(sector: str | None = None, *, include_planned: bool = True) -> dict:
    return {
        "summary": source_registry_summary(),
        "sector": sector,
        "sources": sources_for_sector(sector, include_planned=include_planned),
    }
