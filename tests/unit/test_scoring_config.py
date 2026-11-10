from pathlib import Path

import pytest
from pydantic import ValidationError

from finpilot.scoring.config import MetricConfig, ScoringConfig

from ..conftest import CONFIG_PATH


def test_shipped_config_is_valid() -> None:
    cfg = ScoringConfig.from_yaml(CONFIG_PATH)
    assert set(cfg.categories) == {"growth", "profitability", "valuation", "financial_health"}
    assert sum(c.weight for c in cfg.categories.values()) == pytest.approx(1.0)


def test_rejects_non_increasing_anchors() -> None:
    with pytest.raises(ValidationError):
        MetricConfig(weight=1, anchors=[(0, 10), (0, 20)])


def test_rejects_out_of_range_scores() -> None:
    with pytest.raises(ValidationError):
        MetricConfig(weight=1, anchors=[(0, 10), (1, 120)])


def test_rejects_bad_category_weights(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "methodology_version: x\n"
        "categories:\n"
        "  growth:\n"
        "    weight: 0.5\n"
        "    metrics:\n"
        "      revenue_growth: {weight: 1, anchors: [[0, 0], [1, 100]]}\n"
    )
    with pytest.raises(ValidationError):
        ScoringConfig.from_yaml(bad)
