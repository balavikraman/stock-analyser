from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MarketDataProvider(ABC):
    name = "base"

    @abstractmethod
    def company_snapshot(self, symbol: str) -> dict[str, Any]: ...

    @abstractmethod
    def price_history(self, symbol: str, period: str = "5y") -> list[dict[str, Any]]: ...

    @abstractmethod
    def annual_financials(self, symbol: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def quarterly_financials(self, symbol: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def news(self, symbol: str, company_name: str) -> list[dict[str, Any]]: ...
