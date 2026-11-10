"""Automated quality checks for generated reports (used by the evaluation harness)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from finpilot.domain.models import DISCLAIMER, ResearchResult
from finpilot.reporting.guardrails import find_banned_phrases, report_texts

Severity = Literal["error", "warning"]
_PERCENT = re.compile(r"(-?\d+(?:\.\d+)?)\s?%")
_PERCENT_TOLERANCE = 0.6  # percentage points; allows rounding like 12.4% -> "12%"
_MIN_SECTION_CHARS = 20
_MIN_BULLETS = 2
_SECTOR_CAVEATS = {"Financial Services", "Real Estate", "Utilities"}


@dataclass(frozen=True)
class Finding:
    severity: Severity
    check: str
    message: str


def _allowed_percents(result: ResearchResult) -> list[float]:
    f = result.fundamentals
    values = [f.revenue_growth, f.earnings_growth, f.profit_margin, f.operating_margin]
    return [v * 100 for v in values if v is not None]


def evaluate_result(result: ResearchResult) -> list[Finding]:
    findings: list[Finding] = []
    report = result.report

    if result.disclaimer != DISCLAIMER:
        findings.append(Finding("error", "disclaimer", "Disclaimer text missing or altered"))
    if result.scores.confidence == "low":
        findings.append(Finding("warning", "confidence", "Scores have low confidence"))
    if result.company.sector in _SECTOR_CAVEATS:
        findings.append(
            Finding(
                "warning",
                "sector",
                f"{result.company.sector}: absolute thresholds may mislead (not sector-relative)",
            )
        )

    if report is None:
        findings.append(Finding("error", "report", "No report generated (degraded result)"))
        return findings

    for name, value in report.model_dump().items():
        if isinstance(value, str) and len(value.strip()) < _MIN_SECTION_CHARS:
            findings.append(Finding("error", "sections", f"'{name}' is empty or too short"))
        if isinstance(value, list) and len([v for v in value if str(v).strip()]) < _MIN_BULLETS:
            findings.append(Finding("error", "sections", f"'{name}' has fewer than 2 items"))

    banned = find_banned_phrases(report)
    if banned:
        findings.append(Finding("error", "advisory_language", f"Found: {sorted(set(banned))}"))

    allowed = _allowed_percents(result)
    for text in report_texts(report):
        for token in _PERCENT.findall(text):
            value = float(token)
            if not any(abs(value - a) <= _PERCENT_TOLERANCE for a in allowed):
                findings.append(
                    Finding(
                        "warning",
                        "numbers",
                        f"{token}% does not match any provided metric (check for invention)",
                    )
                )
    return findings
