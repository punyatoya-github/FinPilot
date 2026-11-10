"""Sprint 1 exit criterion: `python -m finpilot.cli MSFT` prints metrics and scores."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from finpilot.core.config import Settings
from finpilot.core.container import build_container
from finpilot.core.errors import FinPilotError
from finpilot.core.logging import configure_logging
from finpilot.domain.models import CompanyData, HealthScores

_METRIC_ROWS: list[tuple[str, str, str]] = [
    ("market_cap", "Market cap", "money"),
    ("revenue", "Revenue", "money"),
    ("revenue_growth", "Revenue growth", "pct"),
    ("eps", "EPS", "num"),
    ("pe_trailing", "P/E (trailing)", "num"),
    ("profit_margin", "Profit margin", "pct"),
    ("operating_margin", "Operating margin", "pct"),
    ("debt_to_equity", "Debt-to-equity", "num"),
    ("total_cash", "Cash", "money"),
]


def _fmt(value: float | None, kind: str) -> str:
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


def format_report(data: CompanyData, scores: HealthScores) -> str:
    p, f = data.profile, data.fundamentals
    lines = [
        f"{p.name} ({p.ticker})  |  {p.sector or 'n/a'} / {p.industry or 'n/a'}",
        f"Data as of {f.data_as_of:%Y-%m-%d %H:%M} UTC",
        "",
        "Key metrics",
    ]
    lines += [f"  {label:<18}{_fmt(getattr(f, attr), kind)}" for attr, label, kind in _METRIC_ROWS]
    lines += ["", "Health scores"]
    for c in scores.categories:
        value = "insufficient data" if c.score is None else f"{c.score:.0f}/100"
        lines.append(f"  {c.category.replace('_', ' ').title():<18}{value}")
        for m in c.components:
            raw = "n/a" if m.raw_value is None else f"{m.raw_value:.3f}"
            sc = "skipped" if m.score is None else f"{m.score:.0f}"
            lines.append(
                f"      {m.metric:<18} raw={raw:<10} score={sc:<8} weight={m.effective_weight:.2f}"
            )
    lines += [
        "",
        f"  Overall           {scores.overall:.0f}/100  "
        f"(confidence: {scores.confidence}, coverage: {scores.coverage:.0%}, "
        f"methodology v{scores.methodology_version})",
        "",
        "Educational use only. Not financial advice.",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="finpilot-cli", description=__doc__)
    parser.add_argument("ticker", help="Stock ticker, e.g. MSFT")
    args = parser.parse_args(argv)

    settings = Settings()
    configure_logging(settings.log_level)
    container = build_container(settings)
    try:
        data = container.provider.get_company(args.ticker)
        scores = container.scoring_engine.score(data.fundamentals)
    except FinPilotError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(format_report(data, scores))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
