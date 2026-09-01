from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from .base import MarketDataProvider


def _num(v: Any) -> float | None:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _statement_rows(frame: pd.DataFrame, quarterly: bool = False) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    out = []
    for col in sorted(frame.columns):
        def get(*names: str) -> float | None:
            for n in names:
                if n in frame.index:
                    return _num(frame.loc[n, col])
            return None
        out.append({"period": pd.Timestamp(col).date().isoformat(), "revenue": get("Total Revenue", "Operating Revenue"), "operating_profit": get("Operating Income", "EBIT"), "net_profit": get("Net Income", "Net Income Common Stockholders"), "eps": get("Diluted EPS", "Basic EPS")})
    return out[-8 if quarterly else -6:]


class YFinanceProvider(MarketDataProvider):
    name = "yfinance"

    def company_snapshot(self, symbol: str) -> dict[str, Any]:
        info = yf.Ticker(symbol).info or {}
        roe = _num(info.get("returnOnEquity")); de = _num(info.get("debtToEquity")); om = _num(info.get("operatingMargins")); nm = _num(info.get("profitMargins")); dy = _num(info.get("dividendYield"))
        return {"symbol": symbol.upper(), "company_name": info.get("longName") or info.get("shortName") or symbol, "sector": info.get("sector"), "industry": info.get("industry"), "currency": info.get("currency") or "INR", "price": _num(info.get("currentPrice") or info.get("regularMarketPrice")), "market_cap": _num(info.get("marketCap")), "pe": _num(info.get("trailingPE")), "forward_pe": _num(info.get("forwardPE")), "pb": _num(info.get("priceToBook")), "roe": roe * 100 if roe is not None else None, "roce": None, "debt_to_equity": de / 100 if de is not None else None, "interest_coverage": None, "operating_margin": om * 100 if om is not None else None, "net_margin": nm * 100 if nm is not None else None, "dividend_yield": dy * 100 if dy is not None else None, "book_value": _num(info.get("bookValue")), "eps": _num(info.get("trailingEps")), "peg": _num(info.get("pegRatio")), "fcf": _num(info.get("freeCashflow")), "operating_cashflow": _num(info.get("operatingCashflow")), "total_debt": _num(info.get("totalDebt")), "total_cash": _num(info.get("totalCash")), "promoter_pledge": None, "52w_high": _num(info.get("fiftyTwoWeekHigh")), "52w_low": _num(info.get("fiftyTwoWeekLow"))}

    def price_history(self, symbol: str, period: str = "5y") -> list[dict[str, Any]]:
        df = yf.download(symbol, period=period, interval="1d", auto_adjust=False, progress=False, threads=False)
        if df.empty: return []
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        return [{"date": pd.Timestamp(i).date().isoformat(), "open": _num(r.get("Open")), "high": _num(r.get("High")), "low": _num(r.get("Low")), "close": _num(r.get("Close")), "volume": _num(r.get("Volume"))} for i, r in df.dropna(subset=["Close"]).iterrows()]

    def annual_financials(self, symbol: str) -> list[dict[str, Any]]:
        t = yf.Ticker(symbol); rows = _statement_rows(t.financials, False); cash = t.cashflow; balance = t.balance_sheet
        for row in rows:
            ts = pd.Timestamp(row["period"])
            matching = [c for c in cash.columns if pd.Timestamp(c).date() == ts.date()] if cash is not None and not cash.empty else []
            if matching:
                c = matching[0]
                for key, names in {"cfo": ("Operating Cash Flow", "Total Cash From Operating Activities"), "capex": ("Capital Expenditure", "Capital Expenditures"), "fcf": ("Free Cash Flow",)}.items():
                    for n in names:
                        if n in cash.index: row[key] = _num(cash.loc[n, c]); break
            matching_b = [c for c in balance.columns if pd.Timestamp(c).date() == ts.date()] if balance is not None and not balance.empty else []
            if matching_b:
                c = matching_b[0]
                for n in ("Total Debt", "Long Term Debt And Capital Lease Obligation"):
                    if n in balance.index: row["debt"] = _num(balance.loc[n, c]); break
        return rows

    def quarterly_financials(self, symbol: str) -> list[dict[str, Any]]:
        return _statement_rows(yf.Ticker(symbol).quarterly_financials, True)

    def news(self, symbol: str, company_name: str) -> list[dict[str, Any]]:
        try: raw = yf.Ticker(symbol).news or []
        except Exception: raw = []
        items = []
        for item in raw[:12]:
            content = item.get("content", item); title = content.get("title") or item.get("title") or "Untitled"; provider = content.get("provider", {}); publisher = provider.get("displayName") if isinstance(provider, dict) else item.get("publisher"); canonical = content.get("canonicalUrl", {}); url = canonical.get("url") if isinstance(canonical, dict) else item.get("link", ""); published = content.get("pubDate") or item.get("providerPublishTime")
            if isinstance(published, (int, float)): published = datetime.fromtimestamp(published, tz=timezone.utc).isoformat()
            items.append({"title": title, "publisher": publisher or "Unknown", "published": published, "url": url or "", "classification": "unclassified", "impact": 0.0, "summary": content.get("summary") or ""})
        return items
