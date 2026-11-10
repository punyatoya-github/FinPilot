from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from finpilot.core.errors import DataProviderError, FinPilotError
from finpilot.domain.models import CompanyData
from finpilot.domain.tickers import normalize_ticker
from finpilot.market_data.normalizer import normalize_info

logger = logging.getLogger(__name__)


def _default_ticker_factory(symbol: str) -> Any:
    import yfinance as yf  # lazy import: keeps tests and imports network/dependency free

    return yf.Ticker(symbol)


class YFinanceProvider:
    """MarketDataProvider backed by yfinance, with retry/backoff.

    `ticker_factory` and `sleep` are injectable so tests never touch the network.
    """

    def __init__(
        self,
        ticker_factory: Callable[[str], Any] | None = None,
        *,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._factory = ticker_factory or _default_ticker_factory
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._sleep = sleep

    def get_company(self, ticker: str) -> CompanyData:
        symbol = normalize_ticker(ticker)
        info = self._fetch_info(symbol)
        data = normalize_info(symbol, info)
        logger.info(
            "fetched company %s (%d fields missing)",
            symbol,
            len(data.fundamentals.missing_fields),
        )
        return data

    def _fetch_info(self, symbol: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                info = self._factory(symbol).info
                if isinstance(info, dict) and info:
                    return info
                last_error = DataProviderError("empty response from yfinance")
            except FinPilotError:
                raise
            except Exception as exc:  # yfinance raises many unrelated exception types
                last_error = exc
            logger.warning("yfinance attempt %d failed for %s: %s", attempt + 1, symbol, last_error)
            if attempt < self._max_retries:
                self._sleep(self._backoff * (2**attempt))
        raise DataProviderError(
            f"yfinance failed for {symbol} after {self._max_retries + 1} attempts: {last_error}"
        )
