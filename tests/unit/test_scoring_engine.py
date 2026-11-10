import pytest

from finpilot.core.errors import InsufficientDataError
from finpilot.domain.models import FundamentalsSnapshot, HealthScores
from finpilot.scoring.engine import ScoringEngine

from ..conftest import make_fundamentals

# Every value below sits exactly on a curve anchor, so expected scores are hand-computable:
#   growth        = 0.6*50 + 0.4*50                  = 50
#   profitability = 0.5*65 + 0.5*90                  = 77.5
#   valuation     = 0.5*80 + 0.5*60                  = 70
#   health        = 0.4*75 + 0.3*90 + 0.3*70         = 78   (cash/debt = 1.0)
#   overall       = .30*50 + .25*77.5 + .20*70 + .25*78


def full_fundamentals(**overrides: float | None) -> FundamentalsSnapshot:
    values: dict[str, float | None] = {
        "revenue_growth": 0.10,
        "earnings_growth": 0.10,
        "profit_margin": 0.15,
        "operating_margin": 0.18,
        "pe_trailing": 20.0,
        "pe_forward": 30.0,
        "debt_to_equity": 1.0,
        "current_ratio": 2.0,
        "total_cash": 100.0,
        "total_debt": 100.0,
    }
    values.update(overrides)
    return make_fundamentals(**values)


def by_category(scores: HealthScores) -> dict[str, float | None]:
    return {c.category: c.score for c in scores.categories}


def test_hand_computed_scores(engine: ScoringEngine) -> None:
    scores = engine.score(full_fundamentals(operating_margin=0.28))
    cats = by_category(scores)
    assert cats["growth"] == pytest.approx(50.0)
    assert cats["profitability"] == pytest.approx(77.5)
    assert cats["valuation"] == pytest.approx(70.0)
    assert cats["financial_health"] == pytest.approx(78.0)
    assert scores.overall == pytest.approx(0.30 * 50 + 0.25 * 77.5 + 0.20 * 70 + 0.25 * 78)
    assert scores.confidence == "high"
    assert scores.coverage == 1.0


def test_is_deterministic(engine: ScoringEngine) -> None:
    f = full_fundamentals()
    assert engine.score(f) == engine.score(f)


def test_missing_metric_renormalizes_weights(engine: ScoringEngine) -> None:
    f = make_fundamentals(
        revenue_growth=0.25, profit_margin=0.15, pe_trailing=20.0, debt_to_equity=1.0
    )
    growth = next(c for c in engine.score(f).categories if c.category == "growth")
    assert growth.status == "ok"
    assert growth.score == pytest.approx(95.0)  # only revenue growth available -> full weight
    effective = {m.metric: m.effective_weight for m in growth.components}
    assert effective == {"revenue_growth": pytest.approx(1.0), "earnings_growth": 0.0}


def test_insufficient_category_is_excluded_and_lowers_confidence(engine: ScoringEngine) -> None:
    f = make_fundamentals(
        profit_margin=0.15,
        operating_margin=0.28,
        pe_trailing=20.0,
        pe_forward=30.0,
        debt_to_equity=1.0,
        current_ratio=2.0,
        total_cash=100.0,
        total_debt=100.0,
    )  # no growth data at all
    scores = engine.score(f)
    growth = next(c for c in scores.categories if c.category == "growth")
    assert growth.status == "insufficient_data" and growth.score is None
    assert growth.effective_weight == 0.0
    assert sum(c.effective_weight for c in scores.categories) == pytest.approx(1.0)
    assert scores.confidence == "medium"


def test_loss_making_company_gets_low_valuation_score(engine: ScoringEngine) -> None:
    scores = engine.score(full_fundamentals(pe_trailing=-12.0, pe_forward=-5.0))
    assert by_category(scores)["valuation"] == pytest.approx(10.0)


def test_no_data_raises(engine: ScoringEngine) -> None:
    with pytest.raises(InsufficientDataError):
        engine.score(make_fundamentals())


def test_scores_stay_within_bounds(engine: ScoringEngine) -> None:
    extreme = full_fundamentals(revenue_growth=9.0, profit_margin=-5.0, debt_to_equity=99.0)
    assert 0 <= engine.score(extreme).overall <= 100
