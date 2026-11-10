from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from finpilot.domain.models import CompanyData
from finpilot.domain.tickers import normalize_ticker
from finpilot.market_data.base import MarketDataProvider

logger = logging.getLogger(__name__)


class CompanyCache(Protocol):
    def get(self, ticker: str) -> tuple[CompanyData, datetime] | None: ...
    def put(self, ticker: str, data: CompanyData, fetched_at: datetime) -> None: ...


class CachingMarketDataProvider:
    """Decorator adding a TTL cache in front of any MarketDataProvider."""

    def __init__(
        self,
        inner: MarketDataProvider,
        cache: CompanyCache,
        ttl: timedelta,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl = ttl
        self._clock = clock

    def get_company(self, ticker: str) -> CompanyData:
        symbol = normalize_ticker(ticker)
        now = self._clock()
        hit = self._cache.get(symbol)
        if hit is not None and now - hit[1] < self._ttl:
            logger.info("company cache hit for %s", symbol)
            return hit[0]
        data = self._inner.get_company(symbol)
        self._cache.put(symbol, data, now)
        return data
