from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from ..evidence import EvidenceRecord


class NSEOfficialEvidenceProvider:
    """Best-effort NSE corporate filing evidence provider.

    NSE's public filing surfaces can change response shape and may require a warmed
    browser-like session. This provider therefore fails closed: unavailable official
    evidence is reported as unavailable and is never guessed.
    """

    name = "nse_official"
    base_url = "https://www.nseindia.com"

    def __init__(self, timeout: float = 12.0) -> None:
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-application",
        }

    @staticmethod
    def _clean_symbol(symbol: str) -> str:
        return symbol.upper().replace(".NS", "").strip()

    @staticmethod
    def _first(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            for key in ("data", "results", "rows", "result"):
                value = data.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
        return []

    @staticmethod
    def _pick(row: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row and row[key] not in (None, ""):
                return row[key]
        lowered = {str(k).lower(): v for k, v in row.items()}
        for key in keys:
            value = lowered.get(key.lower())
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _iso_date(value: Any) -> str | None:
        if value in (None, ""):
            return None
        text = str(value).strip()
        candidates = (
            "%d-%b-%Y %H:%M:%S",
            "%d-%b-%Y",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        )
        for fmt in candidates:
            try:
                dt = datetime.strptime(text[:19], fmt).replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except ValueError:
                continue
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            return None

    def _get_json(self, client: httpx.Client, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        response = client.get(f"{self.base_url}{path}", params=params, headers=self.headers)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            return []
        return self._first(response.json())

    def _session(self) -> httpx.Client:
        client = httpx.Client(timeout=self.timeout, follow_redirects=True)
        # Warm cookies. If this fails, the API requests are still attempted and fail closed.
        try:
            client.get(self.base_url, headers=self.headers)
            client.get(f"{self.base_url}/companies-listing/corporate-filings-application", headers=self.headers)
        except httpx.HTTPError:
            pass
        return client

    def fetch_bundle(self, symbol: str) -> dict[str, Any]:
        nse_symbol = self._clean_symbol(symbol)
        errors: list[str] = []
        announcements: list[dict[str, Any]] = []
        financial_results: list[dict[str, Any]] = []
        shareholding: list[dict[str, Any]] = []

        with self._session() as client:
            calls = (
                ("announcements", "/api/corporate-announcements", {"index": "equities", "symbol": nse_symbol}),
                ("financial_results", "/api/corporates-financial-results", {"index": "equities", "symbol": nse_symbol}),
                ("shareholding", "/api/corporate-share-holdings-master", {"index": "equities", "symbol": nse_symbol}),
            )
            for name, path, params in calls:
                try:
                    rows = self._get_json(client, path, params)
                    if name == "announcements":
                        announcements = rows
                    elif name == "financial_results":
                        financial_results = rows
                    else:
                        shareholding = rows
                except (httpx.HTTPError, ValueError) as exc:
                    errors.append(f"NSE {name} unavailable: {type(exc).__name__}")

        evidence: dict[str, dict[str, Any]] = {}

        if announcements:
            latest = announcements[0]
            observed = self._iso_date(self._pick(latest, "broadcastDateTime", "broadcastDate", "an_dt", "date"))
            evidence["nse_latest_announcement"] = EvidenceRecord(
                value={
                    "subject": self._pick(latest, "subject", "desc", "announcement"),
                    "symbol": self._pick(latest, "symbol") or nse_symbol,
                },
                source="National Stock Exchange of India",
                source_type="exchange_filing",
                observed_at=observed,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.90,
                stale_after_days=45,
                url=f"{self.base_url}/companies-listing/corporate-filings-application?param={nse_symbol}",
            ).to_dict()

        if financial_results:
            latest = financial_results[0]
            observed = self._iso_date(self._pick(latest, "broadcastDateTime", "broadcastDate", "submissionDate", "date"))
            period = self._pick(latest, "periodEnded", "period_ended", "toDate", "period")
            evidence["nse_latest_financial_result"] = EvidenceRecord(
                value={"period": period, "symbol": self._pick(latest, "symbol") or nse_symbol},
                source="National Stock Exchange of India",
                source_type="exchange_filing",
                observed_at=observed,
                period=str(period) if period else None,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.95,
                stale_after_days=180,
                url=f"{self.base_url}/companies-listing/corporate-filings-application?param={nse_symbol}",
            ).to_dict()

        if shareholding:
            latest = shareholding[0]
            observed = self._iso_date(self._pick(latest, "broadcastDateTime", "broadcastDate", "submissionDate", "date"))
            period = self._pick(latest, "asOnDate", "as_on_date", "period")
            evidence["nse_latest_shareholding"] = EvidenceRecord(
                value={"as_on": period, "symbol": self._pick(latest, "symbol") or nse_symbol},
                source="National Stock Exchange of India",
                source_type="exchange_filing",
                observed_at=observed,
                period=str(period) if period else None,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.95,
                stale_after_days=150,
                url=f"{self.base_url}/companies-listing/corporate-filings-application?param={nse_symbol}",
            ).to_dict()

        return {
            "symbol": nse_symbol,
            "announcements": announcements,
            "financial_results": financial_results,
            "shareholding": shareholding,
            "evidence": evidence,
            "errors": errors,
            "source": "National Stock Exchange of India",
        }
