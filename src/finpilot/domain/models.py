"""Core domain models shared across services."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CategoryName = Literal["growth", "profitability", "valuation", "financial_health"]
Confidence = Literal["high", "medium", "low"]


class CompanyProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str
    name: str
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    website: str | None = None
    currency: str = "USD"


class FundamentalsSnapshot(BaseModel):
    """Normalized fundamentals. Ratios are fractions (0.12 = 12%); debt_to_equity is a ratio."""

    model_config = ConfigDict(frozen=True)

    market_cap: float | None = None
    revenue: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    eps: float | None = None
    pe_trailing: float | None = None
    pe_forward: float | None = None
    profit_margin: float | None = None
    operating_margin: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    total_cash: float | None = None
    total_debt: float | None = None
    data_as_of: datetime
    missing_fields: list[str] = Field(default_factory=list)


class CompanyData(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile: CompanyProfile
    fundamentals: FundamentalsSnapshot


class MetricScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    metric: str
    raw_value: float | None
    score: float | None = Field(default=None, ge=0, le=100)
    weight: float  # configured weight within the category
    effective_weight: float  # weight after renormalizing for missing metrics


class CategoryScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: CategoryName
    score: float | None = Field(default=None, ge=0, le=100)
    status: Literal["ok", "insufficient_data"]
    weight: float  # configured weight in the overall score
    effective_weight: float  # weight after renormalizing for insufficient categories
    components: list[MetricScore]


class HealthScores(BaseModel):
    model_config = ConfigDict(frozen=True)

    categories: list[CategoryScore]
    overall: float = Field(ge=0, le=100)
    confidence: Confidence
    coverage: float = Field(ge=0, le=1)  # share of metrics that could be scored
    methodology_version: str


DISCLAIMER = (
    "FinPilot provides educational research only and is not financial, investment, "
    "legal or tax advice. Data may be delayed or inaccurate. Do your own research and "
    "consult a licensed professional before investing."
)


class InvestmentReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    executive_summary: str
    business_overview: str
    bull_case: list[str]
    bear_case: list[str]
    key_strengths: list[str]
    key_risks: list[str]
    financial_health_assessment: str
    growth_outlook: str
    overall_opinion: str  # educational framing; never buy/sell/hold language


class ResearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_id: str
    company: CompanyProfile
    fundamentals: FundamentalsSnapshot
    scores: HealthScores
    report: InvestmentReport | None
    degraded: bool = False
    cached: bool = False
    model: str
    prompt_version: str
    generated_at: datetime
    disclaimer: str = DISCLAIMER
