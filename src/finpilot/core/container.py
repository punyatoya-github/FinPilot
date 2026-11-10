"""Manual dependency wiring. Services depend on Protocols; this is the only place that
picks concrete implementations."""

from __future__ import annotations

from dataclasses import dataclass

from finpilot.core.config import Settings
from finpilot.market_data.base import MarketDataProvider
from finpilot.market_data.yfinance_provider import YFinanceProvider
from finpilot.scoring.config import ScoringConfig
from finpilot.scoring.engine import ScoringEngine


@dataclass(frozen=True)
class Container:
    settings: Settings
    provider: MarketDataProvider
    scoring_engine: ScoringEngine


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    return Container(
        settings=settings,
        provider=YFinanceProvider(
            max_retries=settings.provider_max_retries,
            backoff_seconds=settings.provider_backoff_seconds,
        ),
        scoring_engine=ScoringEngine(ScoringConfig.from_yaml(settings.scoring_config_path)),
    )
