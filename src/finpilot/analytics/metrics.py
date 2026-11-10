"""Pure functions deriving scoring inputs from fundamentals. No I/O."""

from __future__ import annotations

from finpilot.domain.models import FundamentalsSnapshot

CASH_TO_DEBT_CAP = 10.0


def cash_to_debt(cash: float | None, debt: float | None) -> float | None:
    """Cash divided by debt, capped. Debt-free companies get the cap; negatives are invalid."""
    if cash is None or debt is None or cash < 0 or debt < 0:
        return None
    if debt == 0:
        return CASH_TO_DEBT_CAP
    return min(cash / debt, CASH_TO_DEBT_CAP)


def derive_metrics(f: FundamentalsSnapshot) -> dict[str, float | None]:
    """All metric inputs the scoring engine may use, keyed by the names in scoring.yaml."""
    return {
        "revenue_growth": f.revenue_growth,
        "earnings_growth": f.earnings_growth,
        "profit_margin": f.profit_margin,
        "operating_margin": f.operating_margin,
        "pe_trailing": f.pe_trailing,
        "pe_forward": f.pe_forward,
        "debt_to_equity": f.debt_to_equity,
        "current_ratio": f.current_ratio,
        "cash_to_debt": cash_to_debt(f.total_cash, f.total_debt),
    }
