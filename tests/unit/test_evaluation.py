from typing import Any

from finpilot.domain.models import InvestmentReport, ResearchResult
from finpilot.evaluation.checks import evaluate_result
from finpilot.evaluation.runner import evaluate_tickers, render_markdown
from finpilot.market_data.normalizer import normalize_info
from finpilot.scoring.engine import ScoringEngine

from ..fakes import START, FakeClock, FakeGenerator, FakeProvider, canned_report, make_container


def _result(
    engine: ScoringEngine,
    info: dict[str, Any],
    report: InvestmentReport | None,
    **overrides: Any,
) -> ResearchResult:
    data = normalize_info("EXMP", info, now=START)
    return ResearchResult(
        report_id="r",
        company=data.profile,
        fundamentals=data.fundamentals,
        scores=engine.score(data.fundamentals),
        report=report,
        degraded=report is None,
        model="m",
        prompt_version="v",
        generated_at=START,
        **overrides,
    )


def _checks(findings: list[Any]) -> set[tuple[str, str]]:
    return {(f.severity, f.check) for f in findings}


def test_clean_report_has_no_errors(engine: ScoringEngine, sample_info: dict[str, Any]) -> None:
    findings = evaluate_result(_result(engine, sample_info, canned_report()))
    assert not [f for f in findings if f.severity == "error"]


def test_degraded_result_is_an_error(engine: ScoringEngine, sample_info: dict[str, Any]) -> None:
    assert ("error", "report") in _checks(evaluate_result(_result(engine, sample_info, None)))


def test_short_sections_and_few_bullets_are_errors(
    engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    bad = canned_report().model_copy(update={"executive_summary": "Short.", "bull_case": ["one"]})
    findings = evaluate_result(_result(engine, sample_info, bad))
    messages = " ".join(f.message for f in findings if f.check == "sections")
    assert "executive_summary" in messages and "bull_case" in messages


def test_advisory_language_is_an_error(engine: ScoringEngine, sample_info: dict[str, Any]) -> None:
    bad = canned_report().model_copy(
        update={"overall_opinion": "This is a strong buy for everyone."}
    )
    assert ("error", "advisory_language") in _checks(
        evaluate_result(_result(engine, sample_info, bad))
    )


def test_percentages_must_match_provided_metrics(
    engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    ok = canned_report().model_copy(
        update={"growth_outlook": "Revenue grew 12% and operating margin is 44% in the data."}
    )
    assert ("warning", "numbers") not in _checks(evaluate_result(_result(engine, sample_info, ok)))
    invented = canned_report().model_copy(
        update={"growth_outlook": "Revenue is expected to grow 37% next year."}
    )
    flagged = evaluate_result(_result(engine, sample_info, invented))
    assert any(f.check == "numbers" and "37%" in f.message for f in flagged)


def test_sector_and_confidence_warnings(engine: ScoringEngine, sample_info: dict[str, Any]) -> None:
    info = {**sample_info, "sector": "Financial Services"}
    assert ("warning", "sector") in _checks(evaluate_result(_result(engine, info, canned_report())))


def test_tampered_disclaimer_is_an_error(
    engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    result = _result(engine, sample_info, canned_report(), disclaimer="Buy now!")
    assert ("error", "disclaimer") in _checks(evaluate_result(result))


def test_runner_and_markdown(sample_info: dict[str, Any]) -> None:
    container = make_container(FakeProvider(sample_info), FakeGenerator(), FakeClock())
    evaluations = evaluate_tickers(container.research_service, ["EXMP", "bad ticker"])
    assert evaluations[0].errors == 0 and evaluations[0].result is not None
    assert (
        evaluations[1].failure and evaluations[1].errors == 1
    )  # invalid ticker is reported, not raised
    markdown = render_markdown(evaluations)
    assert "| EXMP |" in markdown and "**Failed:**" in markdown and "Executive summary" in markdown
