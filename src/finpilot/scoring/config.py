from __future__ import annotations

from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, Field, model_validator

from finpilot.domain.models import CategoryName


class MetricConfig(BaseModel):
    weight: float = Field(gt=0)
    anchors: list[tuple[float, float]] = Field(min_length=2)
    nonpositive_score: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def _validate_anchors(self) -> Self:
        xs = [x for x, _ in self.anchors]
        if any(b <= a for a, b in zip(xs, xs[1:], strict=False)):
            raise ValueError("anchor x values must be strictly increasing")
        if any(not 0 <= y <= 100 for _, y in self.anchors):
            raise ValueError("anchor scores must be within 0-100")
        return self


class CategoryConfig(BaseModel):
    weight: float = Field(gt=0)
    min_coverage: float = Field(default=0.5, ge=0, le=1)
    metrics: dict[str, MetricConfig] = Field(min_length=1)


class ScoringConfig(BaseModel):
    methodology_version: str
    categories: dict[CategoryName, CategoryConfig]

    @model_validator(mode="after")
    def _validate_weights(self) -> Self:
        total = sum(c.weight for c in self.categories.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"category weights must sum to 1.0, got {total}")
        return self

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        with path.open(encoding="utf-8") as fh:
            return cls.model_validate(yaml.safe_load(fh))
