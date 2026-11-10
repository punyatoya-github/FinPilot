from datetime import UTC, datetime
from typing import Any

import pytest

from finpilot.core.errors import TickerNotFoundError
from finpilot.market_data.normalizer import normalize_info

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_maps_profile_and_fundamentals(sample_info: dict[str, Any]) -> None:
    data = normalize_info("EXMP", sample_info, now=NOW)
    assert data.profile.name == "Example Corp"
    assert data.profile.description == "Makes example software."  # stripped
    assert data.fundamentals.revenue_growth == 0.12
    assert data.fundamentals.pe_trailing == 32.0
    assert data.fundamentals.data_as_of == NOW
    assert data.fundamentals.missing_fields == []


def test_debt_to_equity_converted_from_percent_to_ratio(sample_info: dict[str, Any]) -> None:
    data = normalize_info("EXMP", {**sample_info, "debtToEquity": 150.0}, now=NOW)
    assert data.fundamentals.debt_to_equity == pytest.approx(1.5)


def test_nan_inf_strings_and_bools_become_none(sample_info: dict[str, Any]) -> None:
    info = {
        **sample_info,
        "trailingPE": float("nan"),
        "forwardPE": float("inf"),
        "revenueGrowth": "N/A",
        "currentRatio": True,
    }
    f = normalize_info("EXMP", info, now=NOW).fundamentals
    assert f.pe_trailing is None and f.pe_forward is None
    assert f.revenue_growth is None and f.current_ratio is None
    assert set(f.missing_fields) == {"pe_trailing", "pe_forward", "revenue_growth", "current_ratio"}


def test_falls_back_to_short_name(sample_info: dict[str, Any]) -> None:
    info = {k: v for k, v in sample_info.items() if k != "longName"}
    info["shortName"] = "Example"
    assert normalize_info("EXMP", info, now=NOW).profile.name == "Example"


def test_missing_name_means_ticker_not_found() -> None:
    with pytest.raises(TickerNotFoundError):
        normalize_info("ZZZZ", {"trailingPegRatio": None})
