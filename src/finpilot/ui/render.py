"""Pure functions turning domain objects into display strings/rows (no Gradio imports)."""

from __future__ import annotations

import html

from finpilot.domain.formatting import METRIC_KINDS, METRIC_ROWS, fmt_value
from finpilot.domain.models import (
    CategoryScore,
    CompanyProfile,
    FundamentalsSnapshot,
    HealthScores,
    ResearchResult,
)

REPORT_UNAVAILABLE = (
    "⚠️ The AI report could not be generated right now. The metrics and scores above are "
    "still valid. Try again in a moment."
)


def pretty(name: str) -> str:
    return name.replace("_", " ").title()


def score_band(score: float) -> tuple[str, str]:
    """(label, color) for a 0-100 score."""
    if score >= 70:
        return "Strong", "#2e9e5b"
    if score >= 40:
        return "Moderate", "#d9a21b"
    return "Weak", "#d4493e"


def render_profile(profile: CompanyProfile) -> str:
    where = " · ".join(x for x in (profile.sector, profile.industry) if x)
    lines = [f"## {profile.name} ({profile.ticker})"]
    if where:
        lines.append(f"**{where}**")
    if profile.website:
        lines.append(profile.website)
    if profile.description:
        lines.append(profile.description)
    return "\n\n".join(lines)


def metrics_rows(fundamentals: FundamentalsSnapshot) -> list[list[str]]:
    return [
        [label, fmt_value(getattr(fundamentals, attr), kind)] for attr, label, kind in METRIC_ROWS
    ]


def _bar(label: str, score: float | None, *, big: bool = False) -> str:
    height = 18 if big else 12
    size = "1.15em" if big else "1em"
    title = html.escape(label)
    if score is None:
        return (
            f'<div style="margin:6px 0"><span style="font-size:{size}">{title}</span> '
            '<span style="opacity:.7">insufficient data</span></div>'
        )
    band, color = score_band(score)
    return (
        '<div style="margin:8px 0">'
        f'<div style="display:flex;justify-content:space-between;font-size:{size}">'
        f"<strong>{title}</strong><span>{score:.0f}/100 · {band}</span></div>"
        f'<div style="background:rgba(128,128,128,.25);border-radius:6px;height:{height}px">'
        f'<div style="width:{max(score, 2):.0f}%;background:{color};height:{height}px;'
        'border-radius:6px"></div></div></div>'
    )


def scores_html(scores: HealthScores) -> str:
    bars = [_bar(pretty(c.category), c.score) for c in scores.categories]
    note = (
        f'<div style="opacity:.75;font-size:.9em">Confidence: {html.escape(scores.confidence)} '
        f"· {scores.coverage:.0%} of metrics available</div>"
    )
    return "".join([_bar("Overall score", scores.overall, big=True), *bars, note])


def _category_rows(c: CategoryScore) -> list[list[str]]:
    title = pretty(c.category)
    if c.score is None:
        return [[title, "—", "—", "insufficient data", "—"]]
    rows: list[list[str]] = []
    for i, m in enumerate(c.components):
        kind = METRIC_KINDS.get(m.metric, "num")
        rows.append(
            [
                title if i == 0 else "",
                pretty(m.metric),
                fmt_value(m.raw_value, kind),
                "skipped (no data)" if m.score is None else f"{m.score:.0f}",
                "—" if m.score is None else f"{m.effective_weight:.0%}",
            ]
        )
    return rows


def explanation_rows(scores: HealthScores) -> list[list[str]]:
    rows = [row for c in scores.categories for row in _category_rows(c)]
    rows.append(["Overall", "", "", f"{scores.overall:.0f}", ""])
    return rows


def methodology_note(scores: HealthScores) -> str:
    used = [
        f"{pretty(c.category)} {c.effective_weight:.0%}"
        for c in scores.categories
        if c.score is not None
    ]
    skipped = [pretty(c.category) for c in scores.categories if c.score is None]
    text = (
        "Each metric is converted to a 0-100 score with fixed thresholds "
        f"(methodology v{scores.methodology_version}). A category score is the weighted average "
        "of its available metrics, and the overall score is the weighted average of categories: "
        + ", ".join(used)
        + ". Missing metrics are skipped and the remaining weights are rescaled."
    )
    if skipped:
        text += f" Excluded for lack of data: {', '.join(skipped)}."
    text += (
        " Thresholds are absolute, not sector-relative, so scores for banks, insurers and other "
        "businesses with unusual balance sheets can mislead."
    )
    return text


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def report_sections(result: ResearchResult) -> tuple[str, str, str, str]:
    """Markdown for the four report tabs: summary, bull vs bear, strengths & risks, financials."""
    r = result.report
    if r is None:
        return (REPORT_UNAVAILABLE,) * 4
    return (
        f"### Executive summary\n{r.executive_summary}\n\n"
        f"### Business overview\n{r.business_overview}\n\n"
        f"### Overall assessment\n{r.overall_opinion}",
        f"### Bull case\n{_bullets(r.bull_case)}\n\n### Bear case\n{_bullets(r.bear_case)}",
        f"### Key strengths\n{_bullets(r.key_strengths)}\n\n### Key risks\n{_bullets(r.key_risks)}",
        f"### Financial health\n{r.financial_health_assessment}\n\n"
        f"### Growth outlook\n{r.growth_outlook}",
    )
