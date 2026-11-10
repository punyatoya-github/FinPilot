"""Manual dependency wiring. Services depend on Protocols; this is the only place that
picks concrete implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session, sessionmaker

from finpilot.core.config import Settings
from finpilot.market_data.base import MarketDataProvider
from finpilot.market_data.caching import CachingMarketDataProvider
from finpilot.market_data.yfinance_provider import YFinanceProvider
from finpilot.persistence.db import create_db_engine, init_db, make_session_factory
from finpilot.persistence.repositories import SqlCompanyCacheRepository, SqlReportRepository
from finpilot.reporting.base import ReportGenerator
from finpilot.reporting.openai_generator import OpenAIReportGenerator
from finpilot.reporting.unconfigured import UnconfiguredReportGenerator
from finpilot.research.service import ResearchService
from finpilot.scoring.config import ScoringConfig
from finpilot.scoring.engine import ScoringEngine


@dataclass(frozen=True)
class Container:
    settings: Settings
    provider: MarketDataProvider
    scoring_engine: ScoringEngine
    research_service: ResearchService
    session_factory: sessionmaker[Session]
    openai_configured: bool = False


def _build_generator(settings: Settings) -> ReportGenerator:
    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value():
        return UnconfiguredReportGenerator()
    from openai import OpenAI  # lazy: only needed when a key is configured

    client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_seconds,
    )
    return OpenAIReportGenerator(client, settings.openai_model)


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)

    provider = CachingMarketDataProvider(
        YFinanceProvider(
            max_retries=settings.provider_max_retries,
            backoff_seconds=settings.provider_backoff_seconds,
        ),
        SqlCompanyCacheRepository(session_factory),
        timedelta(hours=settings.data_cache_ttl_hours),
    )
    scoring_engine = ScoringEngine(ScoringConfig.from_yaml(settings.scoring_config_path))
    generator = _build_generator(settings)
    service = ResearchService(
        provider,
        scoring_engine,
        generator,
        SqlReportRepository(session_factory),
        cache_ttl=timedelta(hours=settings.report_cache_ttl_hours),
    )
    return Container(
        settings=settings,
        provider=provider,
        scoring_engine=scoring_engine,
        research_service=service,
        session_factory=session_factory,
        openai_configured=not isinstance(generator, UnconfiguredReportGenerator),
    )
