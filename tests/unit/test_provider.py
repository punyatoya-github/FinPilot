from typing import Any

import pytest

from finpilot.core.errors import DataProviderError, InvalidTickerError, TickerNotFoundError
from finpilot.market_data.yfinance_provider import YFinanceProvider


class FakeTicker:
    def __init__(self, info: Any) -> None:
        self._info = info

    @property
    def info(self) -> Any:
        if isinstance(self._info, Exception):
            raise self._info
        return self._info


def test_success_and_ticker_normalization(sample_info: dict[str, Any]) -> None:
    seen: list[str] = []

    def factory(symbol: str) -> FakeTicker:
        seen.append(symbol)
        return FakeTicker(sample_info)

    data = YFinanceProvider(factory).get_company("  exmp ")
    assert seen == ["EXMP"]
    assert data.profile.ticker == "EXMP"


def test_invalid_ticker_never_hits_provider() -> None:
    def factory(symbol: str) -> FakeTicker:
        raise AssertionError("must not be called")

    with pytest.raises(InvalidTickerError):
        YFinanceProvider(factory).get_company("msft; drop table")


def test_retries_then_succeeds(sample_info: dict[str, Any]) -> None:
    attempts = {"n": 0}
    sleeps: list[float] = []

    def factory(symbol: str) -> FakeTicker:
        attempts["n"] += 1
        return FakeTicker(RuntimeError("rate limited") if attempts["n"] < 3 else sample_info)

    provider = YFinanceProvider(factory, max_retries=2, backoff_seconds=1.0, sleep=sleeps.append)
    assert provider.get_company("EXMP").profile.name == "Example Corp"
    assert attempts["n"] == 3
    assert sleeps == [1.0, 2.0]  # exponential backoff


def test_gives_up_after_max_retries() -> None:
    provider = YFinanceProvider(
        lambda s: FakeTicker({}), max_retries=1, backoff_seconds=0, sleep=lambda _: None
    )
    with pytest.raises(DataProviderError):
        provider.get_company("EXMP")


def test_unknown_ticker_is_not_retried() -> None:
    calls = {"n": 0}

    def factory(symbol: str) -> FakeTicker:
        calls["n"] += 1
        return FakeTicker({"trailingPegRatio": None})  # yfinance's "no such ticker" shape

    with pytest.raises(TickerNotFoundError):
        YFinanceProvider(factory, sleep=lambda _: None).get_company("ZZZZ")
    assert calls["n"] == 1
