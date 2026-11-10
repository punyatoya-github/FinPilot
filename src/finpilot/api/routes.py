from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import text

from finpilot import __version__
from finpilot.api.deps import ContainerDep, ServiceDep
from finpilot.api.schemas import (
    CompanyScoresResponse,
    ErrorResponse,
    HealthResponse,
    ResearchRequest,
    ResearchSummary,
)
from finpilot.domain.models import CompanyData, ResearchResult

router = APIRouter()
_ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
}


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(container: ContainerDep) -> HealthResponse:
    try:
        with container.session_factory() as session:
            session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        version=__version__,
        dependencies={
            "database": database,
            "openai": "configured" if container.openai_configured else "not_configured",
        },
    )


@router.get("/v1/companies/{ticker}", response_model=CompanyData, responses=_ERRORS,
            tags=["companies"])
def get_company(ticker: str, service: ServiceDep) -> CompanyData:
    return service.get_company(ticker)


@router.get("/v1/companies/{ticker}/scores", response_model=CompanyScoresResponse,
            responses=_ERRORS, tags=["companies"])
def get_scores(ticker: str, service: ServiceDep) -> CompanyScoresResponse:
    company, scores = service.get_scores(ticker)
    return CompanyScoresResponse(company=company, scores=scores)


@router.post("/v1/research", response_model=ResearchResult, responses=_ERRORS, tags=["research"])
def create_research(body: ResearchRequest, service: ServiceDep) -> ResearchResult:
    return service.research(body.ticker, refresh=body.refresh)


@router.get("/v1/research", response_model=list[ResearchSummary], responses=_ERRORS,
            tags=["research"])
def list_research(
    service: ServiceDep,
    ticker: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[ResearchSummary]:
    return [
        ResearchSummary(
            report_id=r.report_id,
            ticker=r.company.ticker,
            company_name=r.company.name,
            generated_at=r.generated_at,
            overall_score=r.scores.overall,
            confidence=r.scores.confidence,
            degraded=r.degraded,
        )
        for r in service.list_reports(ticker, limit)
    ]


@router.get("/v1/research/{report_id}", response_model=ResearchResult, responses=_ERRORS,
            tags=["research"])
def get_research(report_id: str, service: ServiceDep) -> ResearchResult:
    return service.get_report(report_id)
