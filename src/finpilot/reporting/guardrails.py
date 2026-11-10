"""Content guardrails: the report must stay educational, never advisory."""

from __future__ import annotations

import re

from finpilot.domain.models import InvestmentReport

_BANNED = [
    r"strong\s+(?:buy|sell)",
    r"(?:buy|sell|hold)\s+rating",
    r"price\s+target",
    r"target\s+price",
    r"guaranteed\s+returns?",
    r"(?:you\s+should|i\s+recommend|we\s+recommend|i\s+suggest|we\s+suggest)\s+"
    r"(?:buy|buying|sell|selling|hold|holding|invest|investing)",
    r"(?:is|are)\s+a\s+(?:buy|sell)\b",
]
_PATTERN = re.compile("|".join(_BANNED), re.IGNORECASE)


def report_texts(report: InvestmentReport) -> list[str]:
    """Every text fragment of the report (strings and list items)."""
    texts: list[str] = []
    for value in report.model_dump().values():
        texts.extend(value if isinstance(value, list) else [value])
    return [t for t in texts if isinstance(t, str)]


def find_banned_phrases(report: InvestmentReport) -> list[str]:
    """Return every advisory phrase found in the report (empty list means clean)."""
    return [m.group(0) for text in report_texts(report) for m in _PATTERN.finditer(text)]
