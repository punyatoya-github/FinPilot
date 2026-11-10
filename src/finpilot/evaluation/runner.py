"""Runs the pipeline over a set of tickers and renders a human-reviewable markdown report."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from finpilot.core.errors import FinPilotError
from finpilot.domain.models import ResearchResult
from finpilot.evaluation.checks import Finding, evaluate_result
from finpilot.research.service import ResearchService

DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "JPM", "KO", "XOM", "TSLA"]


@dataclass(frozen=True)
class TickerEvaluation:
    ticker: str
    seconds: float
    result: ResearchResult | None = None
    failure: str | None = None
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(f.severity == "error" for f in self.findings) + (1 if self.failure else 0)

    @property
    def warnings(self) -> int:
        return sum(f.severity == "warning" for f in self.findings)


def evaluate_tickers(
    service: ResearchService, tickers: list[str], *, refresh: bool = True
) -> list[TickerEvaluation]:
    evaluations: list[TickerEvaluation] = []
    for ticker in tickers:
        started = time.perf_counter()
        try:
            result = service.research(ticker, refresh=refresh)
        except FinPilotError as exc:
            evaluations.append(
                TickerEvaluation(ticker, time.perf_counter() - started, failure=str(exc))
            )
            continue
        evaluations.append(
            TickerEvaluation(
                ticker,
                time.perf_counter() - started,
                result=result,
                findings=evaluate_result(result),
            )
        )
    return evaluations


def render_markdown(evaluations: list[TickerEvaluation]) -> str:
    lines = [
        "# FinPilot report evaluation",
        "",
        "| Ticker | Overall | Confidence | Seconds | Errors | Warnings |",
        "|---|---|---|---|---|---|",
    ]
    for ev in evaluations:
        score = "n/a" if ev.result is None else f"{ev.result.scores.overall:.0f}"
        conf = "n/a" if ev.result is None else ev.result.scores.confidence
        lines.append(
            f"| {ev.ticker} | {score} | {conf} | {ev.seconds:.1f} | {ev.errors} | {ev.warnings} |"
        )
    for ev in evaluations:
        lines += ["", f"## {ev.ticker}"]
        if ev.failure:
            lines.append(f"**Failed:** {ev.failure}")
            continue
        assert ev.result is not None
        lines += [f"**{ev.result.company.name}**", ""]
        lines += [f"- {f.severity.upper()} [{f.check}] {f.message}" for f in ev.findings] or [
            "- No findings"
        ]
        if ev.result.report:
            lines += [
                "",
                "**Executive summary:** " + ev.result.report.executive_summary,
                "",
                "**Overall opinion:** " + ev.result.report.overall_opinion,
            ]
    return "\n".join(lines) + "\n"
