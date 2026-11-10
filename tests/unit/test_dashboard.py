from types import SimpleNamespace
from typing import Any

import gradio as gr

from finpilot.core.rate_limit import RateLimiter
from finpilot.domain.models import CompanyData, HealthScores, ResearchResult
from finpilot.research.service import ResearchService
from finpilot.ui.backends import BackendError
from finpilot.ui.dashboard import PENDING, DashboardView, build_dashboard, make_analyze

from ..fakes import FakeClock, FakeGenerator, FakeProvider, make_container

FIELDS = list(DashboardView.__dataclass_fields__)


def _states(gen: Any) -> list[dict[str, Any]]:
    return [dict(zip(FIELDS, t, strict=True)) for t in gen]


class StubBackend:
    def __init__(
        self,
        real: ResearchService,
        *,
        scores_error: BackendError | None = None,
        research_error: Exception | None = None,
    ) -> None:
        self._service = real
        self.scores_error = scores_error
        self.research_error = research_error
        self.refresh_seen: list[bool] = []

    def company_scores(self, ticker: str) -> tuple[CompanyData, HealthScores]:
        if self.scores_error:
            raise self.scores_error
        return self._service.get_scores(ticker)

    def research(self, ticker: str, refresh: bool = False) -> ResearchResult:
        self.refresh_seen.append(refresh)
        if self.research_error:
            raise self.research_error
        return self._service.research(ticker, refresh=refresh)


def _backend(sample_info: dict[str, Any], **kw: Any) -> StubBackend:
    container = make_container(FakeProvider(sample_info), FakeGenerator(), FakeClock())
    return StubBackend(container.research_service, **kw)


def test_progressive_states(sample_info: dict[str, Any]) -> None:
    states = _states(make_analyze(_backend(sample_info))(" exmp ", False))
    assert len(states) == 3
    assert "Fetching" in states[0]["status"]
    # second state: data visible, report pending
    assert "Example Corp" in states[1]["profile"] and states[1]["scores"]
    assert states[1]["summary"] == PENDING and states[1]["metrics"]
    # final state: report rendered
    final = states[-1]
    assert final["status"].startswith("✅ Example Corp")
    assert "Executive summary" in final["summary"] and "Bull case" in final["bull_bear"]
    assert final["explanation"] and final["methodology"]


def test_refresh_flag_is_forwarded(sample_info: dict[str, Any]) -> None:
    backend = _backend(sample_info)
    list(make_analyze(backend)("EXMP", True))
    assert backend.refresh_seen == [True]


def test_cached_report_is_flagged(sample_info: dict[str, Any]) -> None:
    backend = _backend(sample_info)
    analyze = make_analyze(backend)
    list(analyze("EXMP", False))
    assert "cached report" in _states(analyze("EXMP", False))[-1]["status"]


def test_empty_ticker() -> None:
    states = _states(make_analyze(_backend({}))("   ", False))
    assert len(states) == 1 and "Enter a ticker" in states[0]["status"]


def test_data_error_shows_message_and_stops(sample_info: dict[str, Any]) -> None:
    backend = _backend(sample_info, scores_error=BackendError("TICKER_NOT_FOUND", "No data"))
    states = _states(make_analyze(backend)("ZZZZ", False))
    assert states[-1]["status"] == "❌ No data (`TICKER_NOT_FOUND`)"
    assert states[-1]["profile"] == ""


def test_report_failure_keeps_data_visible(sample_info: dict[str, Any]) -> None:
    backend = _backend(sample_info, research_error=BackendError("LLM_ERROR", "model down"))
    final = _states(make_analyze(backend)("EXMP", False))[-1]
    assert "report failed" in final["status"] and "model down" in final["status"]
    assert "Example Corp" in final["profile"] and final["scores"]
    assert "could not be generated" in final["summary"]


def test_unexpected_errors_are_contained(sample_info: dict[str, Any]) -> None:
    backend = _backend(sample_info, research_error=RuntimeError("boom"))
    final = _states(make_analyze(backend)("EXMP", False))[-1]
    assert "Unexpected error" in final["status"] and "boom" not in final["status"]


def test_rate_limit_applies_per_client(sample_info: dict[str, Any]) -> None:
    limiter = RateLimiter(1, 60, lambda: 0.0)
    analyze = make_analyze(_backend(sample_info), limiter)

    def request(host: str, forwarded: str | None = None) -> Any:
        headers = {"x-forwarded-for": forwarded} if forwarded else {}
        return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers)

    assert len(_states(analyze("EXMP", False, request("1.1.1.1")))) == 3
    blocked = _states(analyze("EXMP", False, request("1.1.1.1")))
    assert len(blocked) == 1 and "Rate limit" in blocked[0]["status"]
    assert len(_states(analyze("EXMP", False, request("2.2.2.2")))) == 3  # other client fine
    # forwarded-for identifies the original client
    assert len(_states(analyze("EXMP", False, request("9.9.9.9", "3.3.3.3")))) == 3
    assert (
        "Rate limit" in _states(analyze("EXMP", False, request("8.8.8.8", "3.3.3.3")))[0]["status"]
    )


def test_build_dashboard_constructs_blocks(sample_info: dict[str, Any]) -> None:
    assert isinstance(build_dashboard(_backend(sample_info)), gr.Blocks)
