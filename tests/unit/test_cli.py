from typing import Any

from finpilot.cli import format_report
from finpilot.market_data.normalizer import normalize_info
from finpilot.scoring.engine import ScoringEngine


def test_format_report_contains_key_sections(
    engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    data = normalize_info("EXMP", sample_info)
    text = format_report(data, engine.score(data.fundamentals))
    assert "Example Corp (EXMP)" in text
    assert "Market cap" in text and "$2.50T" in text
    assert "Overall" in text and "Not financial advice" in text
    assert "Financial Health" in text
