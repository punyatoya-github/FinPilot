"""Generate reports for a set of tickers and check them. Needs network access and an OpenAI key.

    python scripts/evaluate_reports.py                 # default 10 tickers
    python scripts/evaluate_reports.py AAPL KO --out docs/evaluation_report.md

Exits non-zero if any report has an error-level finding.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from finpilot.core.config import Settings
from finpilot.core.container import build_container
from finpilot.core.logging import configure_logging
from finpilot.evaluation.runner import DEFAULT_TICKERS, evaluate_tickers, render_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="*", default=DEFAULT_TICKERS)
    parser.add_argument("--out", type=Path, default=Path("docs/evaluation_report.md"))
    parser.add_argument("--use-cache", action="store_true", help="reuse reports cached < 24h")
    args = parser.parse_args()

    settings = Settings()
    configure_logging(settings.log_level)
    container = build_container(settings)
    if not container.openai_configured:
        print("FINPILOT_OPENAI_API_KEY is not set: reports would all be degraded.", file=sys.stderr)
        return 2

    evaluations = evaluate_tickers(
        container.research_service, args.tickers, refresh=not args.use_cache
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_markdown(evaluations), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 1 if any(ev.errors for ev in evaluations) else 0


if __name__ == "__main__":
    raise SystemExit(main())
