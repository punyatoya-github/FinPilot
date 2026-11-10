from typing import Any

from finpilot.domain.models import CompanyProfile, ResearchResult
from finpilot.market_data.normalizer import normalize_info
from finpilot.scoring.engine import ScoringEngine
from finpilot.ui import render

from ..fakes import START, canned_report


def _result(
    engine: ScoringEngine, info: dict[str, Any], *, degraded: bool = False
) -> ResearchResult:
    data = normalize_info("EXMP", info, now=START)
    return ResearchResult(
        report_id="r",
        company=data.profile,
        fundamentals=data.fundamentals,
        scores=engine.score(data.fundamentals),
        report=None if degraded else canned_report(),
        degraded=degraded,
        model="m",
        prompt_version="v",
        generated_at=START,
    )


def test_profile_markdown() -> None:
    md = render.render_profile(
        CompanyProfile(
            ticker="EXMP",
            name="Example",
            sector="Tech",
            industry="Software",
            description="Does things.",
        )
    )
    assert "## Example (EXMP)" in md and "Tech · Software" in md and "Does things." in md


def test_metrics_rows_format_values(engine: ScoringEngine, sample_info: dict[str, Any]) -> None:
    rows = {
        r[0]: r[1] for r in render.metrics_rows(normalize_info("EXMP", sample_info).fundamentals)
    }
    assert rows["Market cap"] == "$2.50T"
    assert rows["Revenue growth"] == "12.0%"
    assert rows["Debt-to-equity"] == "0.33"


def test_missing_metric_shows_na(engine: ScoringEngine) -> None:
    data = normalize_info("EXMP", {"longName": "X", "profitMargins": 0.2, "operatingMargins": 0.3})
    rows = {r[0]: r[1] for r in render.metrics_rows(data.fundamentals)}
    assert rows["Market cap"] == "n/a" and rows["Profit margin"] == "20.0%"


def test_scores_html_has_all_categories_and_escapes(
    engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    result = _result(engine, sample_info)
    html = render.scores_html(result.scores)
    for label in ("Overall score", "Growth", "Profitability", "Valuation", "Financial Health"):
        assert label in html
    assert "Confidence" in html and "<script" not in html


def test_insufficient_category_is_shown_not_hidden(engine: ScoringEngine) -> None:
    data = normalize_info("EXMP", {"longName": "X", "profitMargins": 0.2, "operatingMargins": 0.3})
    scores = engine.score(data.fundamentals)
    assert "insufficient data" in render.scores_html(scores)
    rows = render.explanation_rows(scores)
    assert any(r[0] == "Growth" and "insufficient" in r[3] for r in rows)
    assert "Excluded for lack of data" in render.methodology_note(scores)


def test_explanation_rows_cover_every_metric(
    engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    scores = _result(engine, sample_info).scores
    rows = render.explanation_rows(scores)
    metric_names = {r[1] for r in rows if r[1]}
    assert {"Revenue Growth", "Pe Trailing", "Cash To Debt"} <= metric_names
    assert rows[-1][0] == "Overall"


def test_score_bands() -> None:
    assert render.score_band(85)[0] == "Strong"
    assert render.score_band(55)[0] == "Moderate"
    assert render.score_band(10)[0] == "Weak"


def test_report_sections(engine: ScoringEngine, sample_info: dict[str, Any]) -> None:
    summary, bull_bear, strengths, financials = render.report_sections(_result(engine, sample_info))
    assert "Executive summary" in summary and "Overall assessment" in summary
    assert "Bull case" in bull_bear and "Bear case" in bull_bear and "- Rich valuation" in bull_bear
    assert "Key risks" in strengths
    assert "Growth outlook" in financials


def test_degraded_report_sections_show_notice(
    engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    sections = render.report_sections(_result(engine, sample_info, degraded=True))
    assert all(s == render.REPORT_UNAVAILABLE for s in sections)
