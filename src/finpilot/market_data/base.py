from __future__ import annotations

from typing import Protocol

from finpilot.domain.models import CompanyData


class MarketDataProvider(Protocol):
    """Abstraction over any fundamentals source (yfinance now; FMP/Polygon later)."""

    def get_company(self, ticker: str) -> CompanyData: ...
