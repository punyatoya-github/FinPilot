from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from finpilot.domain.models import CompanyData, Confidence, HealthScores


class ResearchRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=16, examples=["MSFT"])
    refresh: bool = False


class CompanyScoresResponse(BaseModel):
    company: CompanyData
    scores: HealthScores


class ResearchSummary(BaseModel):
    report_id: str
    ticker: str
    company_name: str
    generated_at: datetime
    overall_score: float
    confidence: Confidence
    degraded: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    dependencies: dict[str, str]


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody
