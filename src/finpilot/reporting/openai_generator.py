from __future__ import annotations

import logging
from typing import Any

from finpilot.core.errors import LLMError, ReportValidationError
from finpilot.domain.models import CompanyData, HealthScores, InvestmentReport
from finpilot.reporting.base import GeneratedReport
from finpilot.reporting.guardrails import find_banned_phrases
from finpilot.reporting.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class OpenAIReportGenerator:
    """Generates the report via OpenAI chat completions in JSON mode.

    The reply is validated against the `InvestmentReport` schema and the advisory-language
    guardrails; invalid output is retried (max_attempts total). API errors are not retried here
    because the OpenAI SDK already retries transient failures.
    """

    def __init__(
        self,
        client: Any,
        model: str,
        *,
        prompt_builder: PromptBuilder | None = None,
        max_attempts: int = 2,
        temperature: float = 0.2,
    ) -> None:
        self._client = client
        self._model = model
        self._prompts = prompt_builder or PromptBuilder()
        self._max_attempts = max_attempts
        self._temperature = temperature

    def generate(self, company: CompanyData, scores: HealthScores) -> GeneratedReport:
        messages = [
            {"role": "system", "content": self._prompts.system_prompt},
            {"role": "user", "content": self._prompts.user_message(company, scores)},
        ]
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    temperature=self._temperature,
                    response_format={"type": "json_object"},
                    messages=messages,
                )
            except Exception as exc:
                raise LLMError(f"OpenAI request failed: {exc}") from exc

            try:
                report = self._parse(response)
                return GeneratedReport(
                    report=report, model=self._model, prompt_version=self._prompts.version
                )
            except (ValueError, ReportValidationError) as exc:  # pydantic errors are ValueErrors
                last_error = exc
                logger.warning("report attempt %d/%d invalid: %s", attempt, self._max_attempts, exc)
        raise LLMError(f"No valid report after {self._max_attempts} attempts: {last_error}")

    @staticmethod
    def _parse(response: Any) -> InvestmentReport:
        content = response.choices[0].message.content
        if not content:
            raise ValueError("empty completion")
        report = InvestmentReport.model_validate_json(content)
        banned = find_banned_phrases(report)
        if banned:
            raise ReportValidationError(f"advisory language found: {banned}")
        return report
