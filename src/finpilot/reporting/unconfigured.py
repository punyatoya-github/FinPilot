from __future__ import annotations

from finpilot.core.errors import LLMError
from finpilot.domain.models import CompanyData, HealthScores
from finpilot.reporting.base import GeneratedReport


class UnconfiguredReportGenerator:
    """Used when no OpenAI key is set: the API still serves metrics and scores (degraded)."""

    def generate(self, company: CompanyData, scores: HealthScores) -> GeneratedReport:
        raise LLMError("OpenAI API key is not configured")
