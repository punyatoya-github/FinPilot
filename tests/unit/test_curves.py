import pytest

from finpilot.scoring.curves import score_value

ANCHORS = [(0.0, 10.0), (0.10, 50.0), (0.25, 95.0)]


def test_exact_anchor() -> None:
    assert score_value(0.10, ANCHORS) == 50.0


def test_interpolates_between_anchors() -> None:
    assert score_value(0.05, ANCHORS) == pytest.approx(30.0)
    assert score_value(0.175, ANCHORS) == pytest.approx(72.5)


def test_clamps_outside_range() -> None:
    assert score_value(-1.0, ANCHORS) == 10.0
    assert score_value(5.0, ANCHORS) == 95.0


def test_decreasing_curve_for_valuation() -> None:
    anchors = [(10.0, 95.0), (20.0, 80.0)]
    assert score_value(15.0, anchors) == pytest.approx(87.5)


def test_nonpositive_override() -> None:
    assert score_value(-5.0, [(10.0, 95.0), (20.0, 80.0)], nonpositive_score=10.0) == 10.0
    assert score_value(0.0, [(10.0, 95.0), (20.0, 80.0)], nonpositive_score=10.0) == 10.0
