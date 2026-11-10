import pytest

from finpilot.reporting.guardrails import find_banned_phrases

from ..fakes import canned_report


def test_clean_report_passes() -> None:
    assert find_banned_phrases(canned_report()) == []


@pytest.mark.parametrize(
    "phrase",
    [
        "This is a Strong Buy.",
        "Our price target is $500.",
        "Analysts have a sell rating on it.",
        "You should buy this stock now.",
        "We recommend holding the shares.",
        "It offers guaranteed returns.",
        "The stock is a buy at these levels.",
    ],
)
def test_detects_advisory_language_in_any_field(phrase: str) -> None:
    report = canned_report().model_copy(update={"bull_case": ["fine", phrase]})
    assert find_banned_phrases(report)


def test_educational_wording_is_not_flagged() -> None:
    report = canned_report().model_copy(
        update={"overall_opinion": "Investors may weigh the valuation against growth."}
    )
    assert find_banned_phrases(report) == []
