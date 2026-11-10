"""Converts a raw yfinance `info` dict into domain models, containing all yfinance quirks."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from finpilot.core.errors import TickerNotFoundError
from finpilot.domain.models import CompanyData, CompanyProfile, FundamentalsSnapshot

# snapshot field -> (yfinance key, optional transform)
_FIELD_MAP: dict[str, tuple[str, Callable[[float], float] | None]] = {
    "market_cap": ("marketCap", None),
    "revenue": ("totalRevenue", None),
    "revenue_growth": ("revenueGrowth", None),
    "earnings_growth": ("earningsGrowth", None),
    "eps": ("trailingEps", None),
    "pe_trailing": ("trailingPE", None),
    "pe_forward": ("forwardPE", None),
    "profit_margin": ("profitMargins", None),
    "operating_margin": ("operatingMargins", None),
    # yfinance reports debt/equity as a percentage (150 == 1.5x); convert to a ratio.
    "debt_to_equity": ("debtToEquity", lambda v: v / 100.0),
    "current_ratio": ("currentRatio", None),
    "total_cash": ("totalCash", None),
    "total_debt": ("totalDebt", None),
}


def _to_float(value: Any) -> float | None:
    """Return a finite float or None. Rejects bools, strings, NaN and infinities."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _clean_str(value: Any) -> str | None:
    return (value.strip() or None) if isinstance(value, str) else None


def normalize_info(
    ticker: str, info: Mapping[str, Any], *, now: datetime | None = None
) -> CompanyData:
    name = _clean_str(info.get("longName")) or _clean_str(info.get("shortName"))
    if name is None:
        raise TickerNotFoundError(ticker)

    values: dict[str, float | None] = {}
    for field, (key, transform) in _FIELD_MAP.items():
        number = _to_float(info.get(key))
        values[field] = transform(number) if (number is not None and transform) else number

    profile = CompanyProfile(
        ticker=ticker,
        name=name,
        sector=_clean_str(info.get("sector")),
        industry=_clean_str(info.get("industry")),
        description=_clean_str(info.get("longBusinessSummary")),
        website=_clean_str(info.get("website")),
        currency=_clean_str(info.get("currency")) or "USD",
    )
    fundamentals = FundamentalsSnapshot(
        **values,
        data_as_of=now or datetime.now(UTC),
        missing_fields=[f for f, v in values.items() if v is None],
    )
    return CompanyData(profile=profile, fundamentals=fundamentals)
