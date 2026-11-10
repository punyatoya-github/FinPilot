from typing import Any

import pytest

from finpilot.core.errors import LLMError
from finpilot.market_data.normalizer import normalize_info
from finpilot.reporting.openai_generator import OpenAIReportGenerator
from finpilot.scoring.engine import ScoringEngine

from ..fakes import FakeChatClient, canned_report

VALID = canned_report().model_dump_json()
BANNED = canned_report().model_copy(update={"overall_opinion": "Strong buy."}).model_dump_json()


def _inputs(engine: ScoringEngine, info: dict[str, Any]) -> tuple[Any, Any]:
    data = normalize_info("EXMP", info)
    return data, engine.score(data.fundamentals)


def test_success(engine: ScoringEngine, sample_info: dict[str, Any]) -> None:
    client = FakeChatClient([VALID])
    result = OpenAIReportGenerator(client, "m1").generate(*_inputs(engine, sample_info))
    assert result.report == canned_report()
    assert result.model == "m1" and result.prompt_version == "report_v1"
    call = client.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["temperature"] == 0.2
    assert [m["role"] for m in call["messages"]] == ["system", "user"]


@pytest.mark.parametrize("bad", ["not json", "{}", "", BANNED])
def test_invalid_output_is_retried_once(
    bad: str, engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    client = FakeChatClient([bad, VALID])
    result = OpenAIReportGenerator(client, "m").generate(*_inputs(engine, sample_info))
    assert result.report == canned_report()
    assert len(client.calls) == 2


def test_gives_up_after_max_attempts(engine: ScoringEngine, sample_info: dict[str, Any]) -> None:
    client = FakeChatClient(["nope", BANNED])
    with pytest.raises(LLMError):
        OpenAIReportGenerator(client, "m", max_attempts=2).generate(*_inputs(engine, sample_info))
    assert len(client.calls) == 2


def test_api_error_is_wrapped_and_not_retried(
    engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    client = FakeChatClient([RuntimeError("boom"), VALID])
    with pytest.raises(LLMError, match="boom"):
        OpenAIReportGenerator(client, "m").generate(*_inputs(engine, sample_info))
    assert len(client.calls) == 1
