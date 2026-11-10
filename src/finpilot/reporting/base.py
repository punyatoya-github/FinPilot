from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from finpilot.domain.models import CompanyData, HealthScores, InvestmentReport


class GeneratedReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    report: InvestmentReport
    model: str
    prompt_version: str


class ReportGenerator(Protocol):
    def generate(self, company: CompanyData, scores: HealthScores) -> GeneratedReport:
        """Produce an educational report. Raises LLMError on failure."""
        ...
