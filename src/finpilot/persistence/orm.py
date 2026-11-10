from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ResearchReportRow(Base):
    __tablename__ = "research_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    prompt_version: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    degraded: Mapped[bool] = mapped_column(default=False)
    result_json: Mapped[str] = mapped_column(Text)  # full ResearchResult; normalize later


class TickerCacheRow(Base):
    __tablename__ = "ticker_cache"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
