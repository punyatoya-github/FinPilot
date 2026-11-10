from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from finpilot.domain.models import CompanyData, ResearchResult
from finpilot.persistence.orm import ResearchReportRow, TickerCacheRow


def _utc(value: datetime) -> datetime:
    """SQLite drops tzinfo; treat naive values as UTC and normalize everything to UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ReportRepository(Protocol):
    def save(self, result: ResearchResult) -> None: ...
    def get(self, report_id: str) -> ResearchResult | None: ...
    def latest(self, ticker: str, *, newer_than: datetime) -> ResearchResult | None: ...
    def list_reports(self, ticker: str | None, limit: int) -> list[ResearchResult]: ...


class SqlReportRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    def save(self, result: ResearchResult) -> None:
        row = ResearchReportRow(
            id=result.report_id,
            ticker=result.company.ticker,
            created_at=_utc(result.generated_at),
            data_as_of=_utc(result.fundamentals.data_as_of),
            prompt_version=result.prompt_version,
            model=result.model,
            degraded=result.degraded,
            result_json=result.model_dump_json(),
        )
        with self._sf() as session:
            session.add(row)
            session.commit()

    def get(self, report_id: str) -> ResearchResult | None:
        with self._sf() as session:
            row = session.get(ResearchReportRow, report_id)
            return None if row is None else ResearchResult.model_validate_json(row.result_json)

    def latest(self, ticker: str, *, newer_than: datetime) -> ResearchResult | None:
        """Newest non-degraded report for the ticker created at or after `newer_than`."""
        stmt = (
            select(ResearchReportRow)
            .where(
                ResearchReportRow.ticker == ticker,
                ResearchReportRow.degraded.is_(False),
                ResearchReportRow.created_at >= _utc(newer_than),
            )
            .order_by(ResearchReportRow.created_at.desc())
            .limit(1)
        )
        with self._sf() as session:
            row = session.scalars(stmt).first()
            return None if row is None else ResearchResult.model_validate_json(row.result_json)

    def list_reports(self, ticker: str | None, limit: int) -> list[ResearchResult]:
        stmt = select(ResearchReportRow).order_by(ResearchReportRow.created_at.desc()).limit(limit)
        if ticker:
            stmt = stmt.where(ResearchReportRow.ticker == ticker)
        with self._sf() as session:
            return [
                ResearchResult.model_validate_json(r.result_json) for r in session.scalars(stmt)
            ]


class SqlCompanyCacheRepository:
    """Implements the market_data CompanyCache protocol on top of the ticker_cache table."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    def get(self, ticker: str) -> tuple[CompanyData, datetime] | None:
        with self._sf() as session:
            row = session.get(TickerCacheRow, ticker)
            if row is None:
                return None
            return CompanyData.model_validate_json(row.payload_json), _utc(row.fetched_at)

    def put(self, ticker: str, data: CompanyData, fetched_at: datetime) -> None:
        with self._sf() as session:
            session.merge(
                TickerCacheRow(
                    ticker=ticker,
                    payload_json=data.model_dump_json(),
                    fetched_at=_utc(fetched_at),
                )
            )
            session.commit()
