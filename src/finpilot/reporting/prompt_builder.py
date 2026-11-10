from __future__ import annotations

import json
from pathlib import Path

from finpilot.domain.models import CompanyData, HealthScores

PROMPT_VERSION = "report_v1"
_DEFAULT_PROMPT = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md"
_MAX_DESCRIPTION_CHARS = 1500


def _sanitize(text: str | None) -> str | None:
    """Strip angle brackets so provider text cannot close our <company_data> delimiter."""
    if text is None:
        return None
    return text.replace("<", "").replace(">", "")[:_MAX_DESCRIPTION_CHARS]


class PromptBuilder:
    def __init__(self, prompt_path: Path = _DEFAULT_PROMPT, version: str = PROMPT_VERSION) -> None:
        self._system = prompt_path.read_text(encoding="utf-8")
        self.version = version

    @property
    def system_prompt(self) -> str:
        return self._system

    def user_message(self, company: CompanyData, scores: HealthScores) -> str:
        profile = company.profile
        payload = {
            "company": {
                "ticker": profile.ticker,
                "name": _sanitize(profile.name),
                "sector": _sanitize(profile.sector),
                "industry": _sanitize(profile.industry),
                "description": _sanitize(profile.description),
            },
            "fundamentals": company.fundamentals.model_dump(
                mode="json", exclude={"missing_fields"}
            ),
            "scores": {
                "overall": round(scores.overall, 1),
                "confidence": scores.confidence,
                "categories": [
                    {
                        "category": c.category,
                        "score": None if c.score is None else round(c.score, 1),
                        "status": c.status,
                        "metrics": [
                            {
                                "metric": m.metric,
                                "raw_value": m.raw_value,
                                "score": None if m.score is None else round(m.score, 1),
                            }
                            for m in c.components
                        ],
                    }
                    for c in scores.categories
                ],
            },
        }
        return (
            "Write the research report as JSON for the company below. "
            "null means the figure is not available.\n"
            f"<company_data>\n{json.dumps(payload, indent=2)}\n</company_data>"
        )
