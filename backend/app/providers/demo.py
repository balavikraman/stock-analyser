from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import sin
from typing import Any

from .base import MarketDataProvider


class DemoProvider(MarketDataProvider):
    name = "demo"

    def company_snapshot(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol.upper(), "company_name": "Demo Compounder Ltd", "sector": "Technology", "industry": "IT Services", "currency": "INR", "price": 1125.0, "market_cap": 470000.0, "pe": 18.2, "pb": 5.4, "roe": 31.0, "roce": 37.0, "debt_to_equity": 0.08, "interest_coverage": 18.0, "operating_margin": 22.4, "net_margin": 16.8, "dividend_yield": 2.8, "book_value": 208.0, "eps": 61.8, "peg": 1.25, "fcf_margin": 15.4, "fcf_conversion": 1.03, "promoter_pledge": 0.0}

    def price_history(self, symbol: str, period: str = "5y") -> list[dict[str, Any]]:
        start = datetime.now(timezone.utc) - timedelta(days=365 * 2)
        rows = []
        price = 860.0
        for i in range(0, 730, 3):
            price = max(600, price + 1.1 + sin(i / 22) * 8)
            rows.append({"date": (start + timedelta(days=i)).date().isoformat(), "open": price - 3, "high": price + 9, "low": price - 10, "close": price, "volume": 1_000_000 + (i % 70) * 9000})
        return rows

    def annual_financials(self, symbol: str) -> list[dict[str, Any]]:
        return [
            {"period": "FY22", "revenue": 82000, "operating_profit": 18400, "net_profit": 13200, "eps": 33.0, "cfo": 14100, "fcf": 12100, "debt": 4800},
            {"period": "FY23", "revenue": 92000, "operating_profit": 20100, "net_profit": 14500, "eps": 36.2, "cfo": 15800, "fcf": 13600, "debt": 3900},
            {"period": "FY24", "revenue": 103000, "operating_profit": 22600, "net_profit": 16400, "eps": 41.0, "cfo": 17100, "fcf": 14800, "debt": 3200},
            {"period": "FY25", "revenue": 116000, "operating_profit": 25700, "net_profit": 18800, "eps": 47.0, "cfo": 19900, "fcf": 17300, "debt": 2500},
            {"period": "FY26", "revenue": 131000, "operating_profit": 29600, "net_profit": 21900, "eps": 54.7, "cfo": 22600, "fcf": 20100, "debt": 1800},
        ]

    def quarterly_financials(self, symbol: str) -> list[dict[str, Any]]:
        return [{"period": "Q2 FY26", "revenue": 31100, "net_profit": 5100, "operating_margin": 21.8}, {"period": "Q3 FY26", "revenue": 32400, "net_profit": 5350, "operating_margin": 22.0}, {"period": "Q4 FY26", "revenue": 33700, "net_profit": 5600, "operating_margin": 22.2}, {"period": "Q1 FY27", "revenue": 35200, "net_profit": 5980, "operating_margin": 22.7}]

    def news(self, symbol: str, company_name: str) -> list[dict[str, Any]]:
        return [{"title": "Large enterprise AI contract signed", "publisher": "Demo source", "published": datetime.now(timezone.utc).isoformat(), "url": "", "classification": "structural_positive", "impact": 0.7, "summary": "Illustrative positive catalyst; replace with live sources in real mode."}, {"title": "Sector pricing remains competitive", "publisher": "Demo source", "published": datetime.now(timezone.utc).isoformat(), "url": "", "classification": "temporary_negative", "impact": -0.25, "summary": "Illustrative risk signal."}]
