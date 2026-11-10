"""Deterministic scoring engine. Pure: same input always yields the same output."""

from __future__ import annotations

import logging

from finpilot.analytics.metrics import derive_metrics
from finpilot.core.errors import InsufficientDataError
from finpilot.domain.models import (
    CategoryName,
    CategoryScore,
    Confidence,
    FundamentalsSnapshot,
    HealthScores,
    MetricScore,
)
from finpilot.scoring.config import CategoryConfig, ScoringConfig
from finpilot.scoring.curves import score_value

logger = logging.getLogger(__name__)


class ScoringEngine:
    def __init__(self, config: ScoringConfig) -> None:
        self._config = config

    def score(self, fundamentals: FundamentalsSnapshot) -> HealthScores:
        metrics = derive_metrics(fundamentals)
        scored = [
            self._score_category(name, cfg, metrics)
            for name, cfg in self._config.categories.items()
        ]

        ok_names = {c.category for c in scored if c.status == "ok"}
        if not ok_names:
            raise InsufficientDataError("No scoring category has enough data")

        total_weight = sum(c.weight for c in scored if c.category in ok_names)
        categories: list[CategoryScore] = []
        overall = 0.0
        for c in scored:
            is_ok = c.category in ok_names and c.score is not None
            effective = c.weight / total_weight if is_ok else 0.0
            categories.append(c.model_copy(update={"effective_weight": effective}))
            if is_ok and c.score is not None:
                overall += c.score * effective

        all_components = [m for c in scored for m in c.components]
        coverage = sum(m.score is not None for m in all_components) / len(all_components)
        result = HealthScores(
            categories=categories,
            overall=overall,
            confidence=self._confidence(len(ok_names), len(scored), coverage),
            coverage=coverage,
            methodology_version=self._config.methodology_version,
        )
        logger.info("scored overall=%.1f confidence=%s", result.overall, result.confidence)
        return result

    @staticmethod
    def _confidence(ok_count: int, total: int, coverage: float) -> Confidence:
        if ok_count == total and coverage >= 0.8:
            return "high"
        if ok_count >= 3 and coverage >= 0.6:
            return "medium"
        return "low"

    @staticmethod
    def _score_category(
        name: CategoryName, cfg: CategoryConfig, metrics: dict[str, float | None]
    ) -> CategoryScore:
        raw_scores: dict[str, float | None] = {}
        for metric, mcfg in cfg.metrics.items():
            value = metrics.get(metric)
            raw_scores[metric] = (
                None if value is None else score_value(value, mcfg.anchors, mcfg.nonpositive_score)
            )

        available_weight = sum(
            cfg.metrics[m].weight for m, s in raw_scores.items() if s is not None
        )
        coverage = sum(s is not None for s in raw_scores.values()) / len(raw_scores)
        sufficient = available_weight > 0 and coverage >= cfg.min_coverage

        components: list[MetricScore] = []
        category_score = 0.0
        for metric, mcfg in cfg.metrics.items():
            s = raw_scores[metric]
            effective = mcfg.weight / available_weight if (sufficient and s is not None) else 0.0
            if s is not None and sufficient:
                category_score += s * effective
            components.append(
                MetricScore(
                    metric=metric,
                    raw_value=metrics.get(metric),
                    score=s,
                    weight=mcfg.weight,
                    effective_weight=effective,
                )
            )
        return CategoryScore(
            category=name,
            score=category_score if sufficient else None,
            status="ok" if sufficient else "insufficient_data",
            weight=cfg.weight,
            effective_weight=0.0,  # filled in by the overall aggregation
            components=components,
        )
