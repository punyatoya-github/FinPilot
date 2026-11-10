from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

from finpilot.domain.models import ResearchResult
from finpilot.market_data.caching import CachingMarketDataProvider
from finpilot.market_data.normalizer import normalize_info
from finpilot.persistence.db import create_db_engine, init_db, make_session_factory
from finpilot.persistence.repositories import SqlCompanyCacheRepository, SqlReportRepository
from finpilot.scoring.engine import ScoringEngine

from ..fakes import START, FakeClock, FakeProvider, canned_report


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    return make_session_factory(engine)


def _result(
    engine: ScoringEngine,
    info: dict[str, Any],
    *,
    report_id: str = "r1",
    ticker: str = "EXMP",
    at: datetime = START,
    degraded: bool = False,
) -> ResearchResult:
    data = normalize_info(ticker, info, now=at)
    return ResearchResult(
        report_id=report_id,
        company=data.profile,
        fundamentals=data.fundamentals,
        scores=engine.score(data.fundamentals),
        report=None if degraded else canned_report(),
        degraded=degraded,
        model="m",
        prompt_version="v",
        generated_at=at,
    )


def test_save_and_get_roundtrip(
    session_factory: sessionmaker[Session], engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    repo = SqlReportRepository(session_factory)
    original = _result(engine, sample_info)
    repo.save(original)
    assert repo.get("r1") == original
    assert repo.get("missing") is None


def test_latest_respects_age_and_ignores_degraded(
    session_factory: sessionmaker[Session], engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    repo = SqlReportRepository(session_factory)
    repo.save(_result(engine, sample_info, report_id="old", at=START - timedelta(hours=30)))
    repo.save(_result(engine, sample_info, report_id="deg", at=START, degraded=True))
    cutoff = START - timedelta(hours=24)
    assert repo.latest("EXMP", newer_than=cutoff) is None  # old is stale, deg is degraded

    repo.save(_result(engine, sample_info, report_id="fresh", at=START - timedelta(hours=1)))
    latest = repo.latest("EXMP", newer_than=cutoff)
    assert latest is not None and latest.report_id == "fresh"
    assert repo.latest("OTHER", newer_than=cutoff) is None


def test_list_orders_newest_first_and_filters(
    session_factory: sessionmaker[Session], engine: ScoringEngine, sample_info: dict[str, Any]
) -> None:
    repo = SqlReportRepository(session_factory)
    repo.save(_result(engine, sample_info, report_id="a", at=START))
    repo.save(_result(engine, sample_info, report_id="b", at=START + timedelta(hours=1)))
    repo.save(
        _result(engine, sample_info, report_id="c", ticker="ZZZ", at=START - timedelta(hours=1))
    )
    assert [r.report_id for r in repo.list_reports(None, 10)] == ["b", "a", "c"]
    assert [r.report_id for r in repo.list_reports("EXMP", 10)] == ["b", "a"]
    assert len(repo.list_reports(None, 1)) == 1


def test_company_cache_roundtrip(
    session_factory: sessionmaker[Session], sample_info: dict[str, Any]
) -> None:
    cache = SqlCompanyCacheRepository(session_factory)
    assert cache.get("EXMP") is None
    data = normalize_info("EXMP", sample_info, now=START)
    cache.put("EXMP", data, START)
    cache.put("EXMP", data, START + timedelta(hours=1))  # upsert
    hit = cache.get("EXMP")
    assert hit is not None
    assert hit[0] == data and hit[1] == START + timedelta(hours=1)
    assert hit[1].tzinfo == UTC


def test_caching_provider_hits_then_expires(
    session_factory: sessionmaker[Session], sample_info: dict[str, Any]
) -> None:
    inner = FakeProvider(sample_info)
    clock = FakeClock()
    provider = CachingMarketDataProvider(
        inner, SqlCompanyCacheRepository(session_factory), timedelta(hours=24), clock
    )
    provider.get_company("exmp")
    provider.get_company("EXMP")
    assert inner.calls == 1  # second call served from cache
    clock.advance(hours=25)
    provider.get_company("EXMP")
    assert inner.calls == 2  # TTL expired
