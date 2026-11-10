from __future__ import annotations

from collections.abc import Sequence


def score_value(
    value: float,
    anchors: Sequence[tuple[float, float]],
    nonpositive_score: float | None = None,
) -> float:
    """Piecewise-linear map of `value` to a score; clamps outside the anchor range.

    If `nonpositive_score` is set and value <= 0, that fixed score is returned
    (e.g. a negative P/E from a loss-making company).
    """
    if nonpositive_score is not None and value <= 0:
        return nonpositive_score
    if value <= anchors[0][0]:
        return anchors[0][1]
    if value >= anchors[-1][0]:
        return anchors[-1][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:], strict=False):
        if x0 <= value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    raise AssertionError("unreachable: anchors must be sorted")  # pragma: no cover
