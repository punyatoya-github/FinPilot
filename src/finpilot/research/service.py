"""Orchestrates the pipeline: data -> scores -> report -> persistence."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from finpilot.core.errors import LLMError, ReportNotFoundError
from finpilot.domain.models import CompanyData, HealthScores, ResearchResult
from finpilot.domain.tickers import normalize_ticker
from finpilot.market_data.base import MarketDataProvider
from finpilot.persistence.repositories import ReportRepository
from finpilot.reporting.base import ReportGenerator
from finpilot.scoring.engine import ScoringEngine

logger = logging.getLogger(__name__)


class ResearchService:
    def __init__(
        self,
        provider: MarketDataProvider,
        scoring_engine: ScoringEngine,
        generator: ReportGenerator,
        reports: ReportRepository,
        *,
        cache_ttl: timedelta = timedelta(hours=24),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._provider = provider
        self._engine = scoring_engine
        self._generator = generator
        self._reports = reports
        self._ttl = cache_ttl
        self._clock = clock

    def get_company(self, ticker: str) -> CompanyData:
        return self._provider.get_company(ticker)

    def get_scores(self, ticker: str) -> tuple[CompanyData, HealthScores]:
        data = self._provider.get_company(ticker)
        return data, self._engine.score(data.fundamentals)

    def research(self, ticker: str, *, refresh: bool = False) -> ResearchResult:
        symbol = normalize_ticker(ticker)
        now = self._clock()

        if not refresh:
            cached = self._reports.latest(symbol, newer_than=now - self._ttl)
            if cached is not None:
                logger.info("report cache hit for %s (%s)", symbol, cached.report_id)
                return cached.model_copy(update={"cached": True})

        data = self._provider.get_company(symbol)
        scores = self._engine.score(data.fundamentals)

        try:
            generated = self._generator.generate(data, scores)
            report, model, prompt_version, degraded = (
                generated.report,
                generated.model,
                generated.prompt_version,
                False,
            )
        except LLMError as exc:
            logger.error("report generation failed for %s, serving degraded: %s", symbol, exc)
            report, model, prompt_version, degraded = None, "n/a", "n/a", True

        result = ResearchResult(
            report_id=uuid.uuid4().hex,
            company=data.profile,
            fundamentals=data.fundamentals,
            scores=scores,
            report=report,
            degraded=degraded,
            model=model,
            prompt_version=prompt_version,
            generated_at=now,
        )
        self._reports.save(result)
        return result

    def get_report(self, report_id: str) -> ResearchResult:
        result = self._reports.get(report_id)
        if result is None:
            raise ReportNotFoundError(report_id)
        return result

    def list_reports(self, ticker: str | None = None, limit: int = 10) -> list[ResearchResult]:
        return self._reports.list_reports(normalize_ticker(ticker) if ticker else None, limit)
