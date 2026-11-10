"""Gradio dashboard. Progressive: metrics and scores appear first, the AI report follows."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import gradio as gr

from finpilot.core.rate_limit import RateLimiter
from finpilot.domain.models import DISCLAIMER
from finpilot.ui import render
from finpilot.ui.backends import BackendError, DashboardBackend

logger = logging.getLogger(__name__)

PENDING = "⏳ Generating AI report… (this can take up to a minute)"
_METRIC_HEADERS = ["Metric", "Value"]
_EXPLANATION_HEADERS = ["Category", "Metric", "Raw value", "Metric score", "Weight in category"]


@dataclass(frozen=True)
class DashboardView:
    """Everything the dashboard shows. `as_tuple` order must match the `outputs` list."""

    status: str = ""
    profile: str = ""
    metrics: list[list[str]] = field(default_factory=list)
    scores: str = ""
    methodology: str = ""
    explanation: list[list[str]] = field(default_factory=list)
    summary: str = ""
    bull_bear: str = ""
    strengths_risks: str = ""
    financials: str = ""

    def as_tuple(self) -> tuple[Any, ...]:
        return (
            self.status,
            self.profile,
            self.metrics,
            self.scores,
            self.methodology,
            self.explanation,
            self.summary,
            self.bull_bear,
            self.strengths_risks,
            self.financials,
        )


def _client_key(request: Any) -> str:
    forwarded = getattr(request, "headers", {}).get("x-forwarded-for", "")
    if forwarded:
        return str(forwarded).split(",")[0].strip()
    client = getattr(request, "client", None)
    return str(getattr(client, "host", "unknown"))


def _error_status(exc: BackendError) -> str:
    return f"❌ {exc.message} (`{exc.code}`)"


def make_analyze(
    backend: DashboardBackend, limiter: RateLimiter | None = None
) -> Callable[..., Iterator[tuple[Any, ...]]]:
    def analyze(
        ticker: str, refresh: bool = False, request: gr.Request | None = None
    ) -> Iterator[tuple[Any, ...]]:
        symbol = (ticker or "").strip().upper()
        if not symbol:
            yield DashboardView(status="Enter a ticker symbol, for example MSFT.").as_tuple()
            return

        if limiter is not None and request is not None:
            wait = limiter.check(_client_key(request))
            if wait > 0:
                yield DashboardView(
                    status=f"⏱️ Rate limit reached. Please try again in {max(1, round(wait))} s."
                ).as_tuple()
                return

        yield DashboardView(status=f"⏳ Fetching data for {symbol}…").as_tuple()
        try:
            company, scores = backend.company_scores(symbol)
        except BackendError as exc:
            yield DashboardView(status=_error_status(exc)).as_tuple()
            return
        except Exception:
            logger.exception("dashboard: unexpected error loading %s", symbol)
            yield DashboardView(status="❌ Unexpected error while loading data.").as_tuple()
            return

        base = DashboardView(
            profile=render.render_profile(company.profile),
            metrics=render.metrics_rows(company.fundamentals),
            scores=render.scores_html(scores),
            methodology=render.methodology_note(scores),
            explanation=render.explanation_rows(scores),
        )
        pending = {
            "summary": PENDING,
            "bull_bear": PENDING,
            "strengths_risks": PENDING,
            "financials": PENDING,
        }
        yield _with(base, status=f"✅ Data loaded for {symbol}. Writing the report…", **pending)

        try:
            result = backend.research(symbol, refresh)
        except BackendError as exc:
            failed = {k: render.REPORT_UNAVAILABLE for k in pending}
            yield _with(
                base, status=f"Data loaded, but the report failed: {_error_status(exc)}", **failed
            )
            return
        except Exception:
            logger.exception("dashboard: unexpected error researching %s", symbol)
            failed = {k: render.REPORT_UNAVAILABLE for k in pending}
            yield _with(base, status="❌ Unexpected error while generating the report.", **failed)
            return

        summary, bull_bear, strengths_risks, financials = render.report_sections(result)
        flags = (" · cached report" if result.cached else "") + (
            " · ⚠️ report unavailable" if result.degraded else ""
        )
        status = (
            f"✅ {result.company.name} · data as of "
            f"{result.fundamentals.data_as_of:%Y-%m-%d %H:%M} UTC{flags}"
        )
        yield _with(
            DashboardView(
                profile=render.render_profile(result.company),
                metrics=render.metrics_rows(result.fundamentals),
                scores=render.scores_html(result.scores),
                methodology=render.methodology_note(result.scores),
                explanation=render.explanation_rows(result.scores),
            ),
            status=status,
            summary=summary,
            bull_bear=bull_bear,
            strengths_risks=strengths_risks,
            financials=financials,
        )

    return analyze


def _with(view: DashboardView, **changes: Any) -> tuple[Any, ...]:
    return DashboardView(**{**view.__dict__, **changes}).as_tuple()


def build_dashboard(backend: DashboardBackend, limiter: RateLimiter | None = None) -> gr.Blocks:
    analyze = make_analyze(backend, limiter)
    with gr.Blocks(title="FinPilot") as demo:
        gr.Markdown("# 📈 FinPilot\nAI investment research co-pilot for retail investors")
        gr.Markdown(f"> ⚠️ **{DISCLAIMER}**")
        with gr.Row():
            ticker = gr.Textbox(label="Ticker", placeholder="e.g. MSFT", max_lines=1, scale=3)
            refresh = gr.Checkbox(label="Force refresh", value=False, scale=1)
            go = gr.Button("Analyze", variant="primary", scale=1)
        gr.Examples(examples=[["MSFT"], ["NVDA"], ["AAPL"], ["GOOGL"], ["AMZN"]], inputs=[ticker])
        status = gr.Markdown()
        with gr.Row():
            with gr.Column(scale=2):
                profile = gr.Markdown()
            with gr.Column(scale=1):
                metrics = gr.Dataframe(
                    headers=_METRIC_HEADERS, interactive=False, label="Key metrics"
                )
        scores = gr.HTML()
        with gr.Accordion("How the scores are calculated", open=False):
            methodology = gr.Markdown()
            explanation = gr.Dataframe(headers=_EXPLANATION_HEADERS, interactive=False)
        with gr.Tabs():
            with gr.Tab("Summary"):
                summary = gr.Markdown()
            with gr.Tab("Bull vs bear"):
                bull_bear = gr.Markdown()
            with gr.Tab("Strengths & risks"):
                strengths_risks = gr.Markdown()
            with gr.Tab("Financials & growth"):
                financials = gr.Markdown()

        outputs = [
            status,
            profile,
            metrics,
            scores,
            methodology,
            explanation,
            summary,
            bull_bear,
            strengths_risks,
            financials,
        ]
        go.click(analyze, [ticker, refresh], outputs, api_name="analyze")
        ticker.submit(analyze, [ticker, refresh], outputs, api_name=False)
    return demo
