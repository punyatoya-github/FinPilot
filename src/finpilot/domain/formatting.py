"""Display formatting shared by the CLI and the dashboard."""

from __future__ import annotations

# (FundamentalsSnapshot attribute, label, kind)
METRIC_ROWS: list[tuple[str, str, str]] = [
    ("market_cap", "Market cap", "money"),
    ("revenue", "Revenue", "money"),
    ("revenue_growth", "Revenue growth", "pct"),
    ("earnings_growth", "Earnings growth", "pct"),
    ("eps", "EPS", "num"),
    ("pe_trailing", "P/E (trailing)", "num"),
    ("pe_forward", "P/E (forward)", "num"),
    ("profit_margin", "Profit margin", "pct"),
    ("operating_margin", "Operating margin", "pct"),
    ("debt_to_equity", "Debt-to-equity", "num"),
    ("current_ratio", "Current ratio", "num"),
    ("total_cash", "Cash", "money"),
    ("total_debt", "Total debt", "money"),
]

METRIC_KINDS: dict[str, str] = {
    "revenue_growth": "pct",
    "earnings_growth": "pct",
    "profit_margin": "pct",
    "operating_margin": "pct",
}


def fmt_value(value: float | None, kind: str) -> str:
    if value is None:
        return "n/a"
    if kind == "pct":
        return f"{value * 100:.1f}%"
    if kind == "money":
        for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
            if abs(value) >= limit:
                return f"${value / limit:.2f}{suffix}"
        return f"${value:,.0f}"
    return f"{value:.2f}"
