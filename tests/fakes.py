"""Test doubles shared by unit and integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from finpilot.core.config import Settings
from finpilot.core.container import Container
from finpilot.domain.models import CompanyData, HealthScores, InvestmentReport
from finpilot.domain.tickers import normalize_ticker
from finpilot.market_data.normalizer import normalize_info
from finpilot.persistence.db import create_db_engine, init_db, make_session_factory
from finpilot.persistence.repositories import SqlReportRepository
from finpilot.reporting.base import GeneratedReport
from finpilot.research.service import ResearchService
from finpilot.scoring.config import ScoringConfig
from finpilot.scoring.engine import ScoringEngine

from .conftest import CONFIG_PATH

START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def canned_report() -> InvestmentReport:
    return InvestmentReport(
        executive_summary="A profitable example company.",
        business_overview="Makes example software (general knowledge; verify with filings).",
        bull_case=["Strong margins", "Healthy growth"],
        bear_case=["Rich valuation", "Competition"],
        key_strengths=["Profitability"],
        key_risks=["Valuation risk"],
        financial_health_assessment="Balance sheet looks solid.",
        growth_outlook="Growth is solid relative to thresholds.",
        overall_opinion="Fundamentals look strong; weigh valuation carefully.",
    )


class FakeClock:
    def __init__(self, now: datetime = START) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


class FakeProvider:
    def __init__(self, info: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.info = info
        self.error = error
        self.calls = 0

    def get_company(self, ticker: str) -> CompanyData:
        self.calls += 1
        symbol = normalize_ticker(ticker)
        if self.error:
            raise self.error
        assert self.info is not None
        return normalize_info(symbol, self.info, now=START)


class FakeGenerator:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def generate(self, company: CompanyData, scores: HealthScores) -> GeneratedReport:
        self.calls += 1
        if self.error:
            raise self.error
        return GeneratedReport(report=canned_report(), model="fake-model", prompt_version="test_v1")


class FakeChatClient:
    """Mimics `client.chat.completions.create` of the OpenAI SDK."""

    def __init__(self, responses: list[str | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=item))])


def make_container(
    provider: FakeProvider, generator: FakeGenerator, clock: FakeClock | None = None
) -> Container:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    session_factory = make_session_factory(engine)
    scoring = ScoringEngine(ScoringConfig.from_yaml(CONFIG_PATH))
    service = ResearchService(
        provider, scoring, generator, SqlReportRepository(session_factory),
        clock=clock or FakeClock(),
    )
    return Container(
        settings=Settings(),
        provider=provider,
        scoring_engine=scoring,
        research_service=service,
        session_factory=session_factory,
        openai_configured=True,
    )
