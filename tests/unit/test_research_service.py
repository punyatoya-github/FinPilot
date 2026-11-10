from typing import Any

import pytest

from finpilot.core.errors import (
    DataProviderError,
    InsufficientDataError,
    InvalidTickerError,
    LLMError,
    ReportNotFoundError,
)

from ..fakes import FakeClock, FakeGenerator, FakeProvider, make_container


def _service(
    info: dict[str, Any] | None,
    generator: FakeGenerator | None = None,
    provider_error: Exception | None = None,
) -> tuple[Any, FakeProvider, FakeGenerator, FakeClock]:
    provider = FakeProvider(info, provider_error)
    gen = generator or FakeGenerator()
    clock = FakeClock()
    return make_container(provider, gen, clock).research_service, provider, gen, clock


def test_happy_path(sample_info: dict[str, Any]) -> None:
    service, _, gen, _ = _service(sample_info)
    result = service.research("msft")
    assert result.company.ticker == "MSFT"
    assert result.report is not None and not result.degraded and not result.cached
    assert 0 <= result.scores.overall <= 100
    assert result.model == "fake-model" and "not financial" in result.disclaimer
    assert gen.calls == 1
    assert service.get_report(result.report_id) == result


def test_second_call_is_served_from_cache(sample_info: dict[str, Any]) -> None:
    service, provider, gen, _ = _service(sample_info)
    first = service.research("EXMP")
    second = service.research("EXMP")
    assert second.cached is True and second.report_id == first.report_id
    assert gen.calls == 1 and provider.calls == 1


def test_refresh_bypasses_cache(sample_info: dict[str, Any]) -> None:
    service, _, gen, _ = _service(sample_info)
    first = service.research("EXMP")
    second = service.research("EXMP", refresh=True)
    assert second.report_id != first.report_id and gen.calls == 2


def test_cache_expires(sample_info: dict[str, Any]) -> None:
    service, _, gen, clock = _service(sample_info)
    service.research("EXMP")
    clock.advance(hours=25)
    service.research("EXMP")
    assert gen.calls == 2


def test_llm_failure_degrades_and_is_not_cached(sample_info: dict[str, Any]) -> None:
    gen = FakeGenerator(error=LLMError("down"))
    service, _, _, _ = _service(sample_info, gen)
    result = service.research("EXMP")
    assert result.degraded and result.report is None and result.scores.overall > 0
    again = service.research("EXMP")
    # degraded results are never served from cache
    assert again.report_id != result.report_id and gen.calls == 2


def test_provider_error_propagates() -> None:
    service, *_ = _service(None, provider_error=DataProviderError("down"))
    with pytest.raises(DataProviderError):
        service.research("EXMP")


def test_insufficient_data_propagates() -> None:
    service, *_ = _service({"longName": "Empty Co"})
    with pytest.raises(InsufficientDataError):
        service.research("EMPT")


def test_invalid_ticker_and_missing_report(sample_info: dict[str, Any]) -> None:
    service, *_ = _service(sample_info)
    with pytest.raises(InvalidTickerError):
        service.research("bad ticker!")
    with pytest.raises(ReportNotFoundError):
        service.get_report("nope")
