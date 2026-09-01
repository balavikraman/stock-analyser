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


SOURCES: tuple[SourceDefinition, ...] = (
    SourceDefinition("nse_filings", "NSE Corporate Filings", "exchange", "official", "public-web", "active", "https://www.nseindia.com/companies-listing/corporate-filings-financial-results", ("financial_results", "announcements", "shareholding", "xbrl", "corporate_actions"), priority=100, notes="Primary exchange evidence. Endpoint/document failures must fail closed."),
    SourceDefinition("company_ir", "Company Investor Relations", "company_filing", "official", "public-web", "active", "company-specific", ("annual_reports", "quarterly_results", "presentations", "earnings_releases", "guidance", "transcripts"), priority=98, notes="Bounded issuer-domain discovery; documents remain auditable and unsupported labels are not guessed."),
    SourceDefinition("bse_public", "BSE Public Corporate Filings", "exchange", "official", "public-web", "active", "https://www.bseindia.com/", ("financial_results", "announcements", "shareholding", "corporate_actions", "governance"), priority=96, notes="Bounded public-page discovery by six-digit BSE scrip code; no undocumented data-feed API or document download."),
    SourceDefinition("sebi_filings", "SEBI Filings and Orders", "regulator", "official", "public-web", "active", "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3", ("offer_documents", "takeovers", "regulatory_filings", "orders", "enforcement"), priority=95, notes="Bounded latest-listing discovery with local entity-name filtering; absence is never treated as a complete historical search."),
    SourceDefinition("rbi", "Reserve Bank of India / DBIE", "regulator", "official", "public-web", "planned", "https://data.rbi.org.in/", ("rates", "banking_system", "credit", "deposits", "fx", "inflation", "liquidity", "macro"), ("banks", "nbfc", "financials", "all"), "daily/monthly/quarterly", 94),
    SourceDefinition("trai", "TRAI Performance Indicators", "regulator", "official", "public-web", "planned", "https://www.trai.gov.in/release-publication/reports/performance-indicators-reports", ("subscribers", "market_size", "usage", "arpu_context", "qos", "broadband"), ("telecom",), "monthly/quarterly", 92),
    SourceDefinition("ppac", "Petroleum Planning & Analysis Cell", "government", "official", "public-web", "planned", "https://ppac.gov.in/", ("natural_gas_consumption", "petroleum_consumption", "prices", "imports", "sector_demand"), ("oil_gas", "energy", "gas_utilities"), "monthly", 92),
    SourceDefinition("cea", "Central Electricity Authority", "government", "official", "public-web", "planned", "https://cea.nic.in/", ("installed_capacity", "generation", "power_demand", "plant_load_factor", "transmission"), ("power", "utilities", "renewables"), "daily/monthly", 92),
    SourceDefinition("steel_ministry", "Ministry of Steel", "government", "official", "public-web", "planned", "https://steel.gov.in/", ("steel_production", "consumption", "prices", "imports", "exports", "industry_reports"), ("steel", "metals"), "monthly", 90),
    SourceDefinition("coal_ministry", "Ministry of Coal", "government", "official", "public-web", "planned", "https://coal.gov.in/", ("coal_production", "dispatch", "imports", "sector_supply"), ("coal", "power", "energy"), "monthly", 90),
    SourceDefinition("yfinance", "Yahoo Finance via yfinance", "aggregator", "secondary", "public-library", "active", "https://finance.yahoo.com/", ("prices", "price_history", "snapshot_ratios", "normalized_financials", "news_links"), priority=60, notes="Convenience/secondary source. Important facts should be cross-checked against official evidence."),
)


def _sector_tokens(sector: str | None) -> set[str]:
    text = (sector or "").lower().replace("&", " ").replace("/", " ").replace("-", " ")
    tokens = {part.strip() for part in text.split() if part.strip()}
    aliases = {"bank": "banks", "banking": "banks", "financial": "financials", "telecommunications": "telecom", "telecommunication": "telecom", "oil": "oil_gas", "gas": "oil_gas", "electric": "power", "electricity": "power", "metal": "metals"}
    tokens.update(aliases[token] for token in list(tokens) if token in aliases)
    return tokens


def sources_for_sector(sector: str | None, *, include_planned: bool = True) -> list[dict]:
    tokens = _sector_tokens(sector)
    selected = []
    for source in SOURCES:
        if not include_planned and source.adapter_status != "active":
            continue
        if "all" in source.sectors or not tokens or tokens.intersection(source.sectors):
            selected.append(source)
    selected.sort(key=lambda item: item.priority, reverse=True)
    return [source.to_dict() for source in selected]


def source_registry_summary(sources: Iterable[SourceDefinition] = SOURCES) -> dict:
    rows = list(sources)
    return {"total": len(rows), "active": sum(1 for source in rows if source.adapter_status == "active"), "planned": sum(1 for source in rows if source.adapter_status == "planned"), "official": sum(1 for source in rows if source.authority == "official"), "free_public_strategy": True, "policy": "official/regulator/company sources first; secondary aggregators for convenience and cross-checking; missing evidence is never guessed"}


def registry_payload(sector: str | None = None, *, include_planned: bool = True) -> dict:
    return {"summary": source_registry_summary(), "sector": sector, "sources": sources_for_sector(sector, include_planned=include_planned)}
