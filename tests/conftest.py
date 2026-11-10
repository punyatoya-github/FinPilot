from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from finpilot.domain.models import FundamentalsSnapshot
from finpilot.scoring.config import ScoringConfig
from finpilot.scoring.engine import ScoringEngine

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "scoring.yaml"
NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def scoring_config() -> ScoringConfig:
    return ScoringConfig.from_yaml(CONFIG_PATH)


@pytest.fixture
def engine(scoring_config: ScoringConfig) -> ScoringEngine:
    return ScoringEngine(scoring_config)


def make_fundamentals(**overrides: Any) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(data_as_of=NOW, **overrides)


@pytest.fixture
def sample_info() -> dict[str, Any]:
    """Synthetic yfinance-style payload (not real company data)."""
    return {
        "longName": "Example Corp",
        "sector": "Technology",
        "industry": "Software",
        "longBusinessSummary": "  Makes example software.  ",
        "website": "https://example.com",
        "currency": "USD",
        "marketCap": 2_500_000_000_000,
        "totalRevenue": 250_000_000_000,
        "revenueGrowth": 0.12,
        "earningsGrowth": 0.15,
        "trailingEps": 11.5,
        "trailingPE": 32.0,
        "forwardPE": 28.0,
        "profitMargins": 0.36,
        "operatingMargins": 0.44,
        "debtToEquity": 33.0,
        "currentRatio": 1.3,
        "totalCash": 80_000_000_000,
        "totalDebt": 60_000_000_000,
    }
