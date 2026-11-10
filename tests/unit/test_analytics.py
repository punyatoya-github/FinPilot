import pytest

from finpilot.analytics.metrics import CASH_TO_DEBT_CAP, cash_to_debt, derive_metrics

from ..conftest import make_fundamentals


def test_cash_to_debt_basic() -> None:
    assert cash_to_debt(50, 100) == 0.5


def test_cash_to_debt_zero_debt_is_capped() -> None:
    assert cash_to_debt(50, 0) == CASH_TO_DEBT_CAP


def test_cash_to_debt_large_ratio_is_capped() -> None:
    assert cash_to_debt(1000, 1) == CASH_TO_DEBT_CAP


@pytest.mark.parametrize("cash,debt", [(None, 1), (1, None), (-1, 1), (1, -1)])
def test_cash_to_debt_invalid(cash: float | None, debt: float | None) -> None:
    assert cash_to_debt(cash, debt) is None


def test_derive_metrics_includes_cash_to_debt() -> None:
    f = make_fundamentals(revenue_growth=0.1, total_cash=10, total_debt=20)
    m = derive_metrics(f)
    assert m["revenue_growth"] == 0.1
    assert m["cash_to_debt"] == 0.5
    assert m["pe_trailing"] is None
