from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from finpilot.core.errors import DataProviderError, LLMError, TickerNotFoundError
from finpilot.main import create_app

from ..fakes import FakeGenerator, FakeProvider, make_container


@pytest.fixture
def parts(sample_info: dict[str, Any]) -> tuple[FakeProvider, FakeGenerator]:
    return FakeProvider(sample_info), FakeGenerator()


@pytest.fixture
def client(parts: tuple[FakeProvider, FakeGenerator]) -> Iterator[TestClient]:
    with TestClient(create_app(make_container(*parts)), raise_server_exceptions=False) as c:
        yield c


def _assert_error(resp: Any, status: int, code: str) -> None:
    assert resp.status_code == status
    body = resp.json()["error"]
    assert body["code"] == code and body["message"]
    assert body["request_id"] == resp.headers["X-Request-ID"]


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["dependencies"] == {"database": "ok", "openai": "configured"}


def test_company_endpoint(client: TestClient) -> None:
    body = client.get("/v1/companies/exmp").json()
    assert body["profile"]["ticker"] == "EXMP"
    assert body["fundamentals"]["revenue_growth"] == 0.12


def test_scores_endpoint_has_explanations(client: TestClient) -> None:
    body = client.get("/v1/companies/EXMP/scores").json()
    cats = {c["category"]: c for c in body["scores"]["categories"]}
    assert set(cats) == {"growth", "profitability", "valuation", "financial_health"}
    assert cats["growth"]["components"][0]["metric"] == "revenue_growth"
    assert 0 <= body["scores"]["overall"] <= 100


def test_research_flow_create_get_list(client: TestClient) -> None:
    created = client.post("/v1/research", json={"ticker": "EXMP"})
    assert created.status_code == 200
    body = created.json()
    assert body["report"]["executive_summary"] and body["degraded"] is False
    assert "not financial" in body["disclaimer"]

    fetched = client.get(f"/v1/research/{body['report_id']}")
    assert fetched.status_code == 200 and fetched.json()["report_id"] == body["report_id"]

    listing = client.get("/v1/research", params={"ticker": "EXMP", "limit": 5}).json()
    assert [r["report_id"] for r in listing] == [body["report_id"]]
    assert listing[0]["company_name"] == "Example Corp"


def test_repeat_request_is_cached_and_refresh_regenerates(
    client: TestClient, parts: tuple[FakeProvider, FakeGenerator]
) -> None:
    _, generator = parts
    client.post("/v1/research", json={"ticker": "EXMP"})
    cached = client.post("/v1/research", json={"ticker": "EXMP"}).json()
    assert cached["cached"] is True and generator.calls == 1
    client.post("/v1/research", json={"ticker": "EXMP", "refresh": True})
    assert generator.calls == 2


def test_llm_failure_returns_degraded_200(sample_info: dict[str, Any]) -> None:
    container = make_container(FakeProvider(sample_info), FakeGenerator(LLMError("down")))
    with TestClient(create_app(container)) as c:
        body = c.post("/v1/research", json={"ticker": "EXMP"}).json()
    assert body["degraded"] is True and body["report"] is None and body["scores"]["overall"] > 0


def test_invalid_ticker_is_400(client: TestClient) -> None:
    _assert_error(client.get("/v1/companies/bad;ticker"), 400, "INVALID_TICKER")
    _assert_error(client.post("/v1/research", json={"ticker": "a b"}), 400, "INVALID_TICKER")


def test_unknown_ticker_is_404(sample_info: dict[str, Any]) -> None:
    provider = FakeProvider(error=TickerNotFoundError("ZZZZ"))
    with TestClient(create_app(make_container(provider, FakeGenerator()))) as c:
        _assert_error(c.get("/v1/companies/ZZZZ"), 404, "TICKER_NOT_FOUND")


def test_provider_failure_is_502() -> None:
    provider = FakeProvider(error=DataProviderError("yahoo down"))
    with TestClient(create_app(make_container(provider, FakeGenerator()))) as c:
        _assert_error(c.post("/v1/research", json={"ticker": "EXMP"}), 502, "DATA_PROVIDER_ERROR")


def test_insufficient_data_is_422() -> None:
    provider = FakeProvider({"longName": "Empty Co"})
    with TestClient(create_app(make_container(provider, FakeGenerator()))) as c:
        _assert_error(c.get("/v1/companies/EMPT/scores"), 422, "INSUFFICIENT_DATA")


def test_report_not_found_is_404(client: TestClient) -> None:
    _assert_error(client.get("/v1/research/doesnotexist"), 404, "REPORT_NOT_FOUND")


def test_schema_validation_is_422_with_envelope(client: TestClient) -> None:
    _assert_error(client.post("/v1/research", json={}), 422, "VALIDATION_ERROR")
    _assert_error(client.get("/v1/research", params={"limit": 0}), 422, "VALIDATION_ERROR")


def test_unexpected_error_is_500_without_leaking_details(
    sample_info: dict[str, Any],
) -> None:
    provider = FakeProvider(error=RuntimeError("secret internals"))
    with TestClient(
        create_app(make_container(provider, FakeGenerator())), raise_server_exceptions=False
    ) as c:
        resp = c.get("/v1/companies/EXMP")
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in resp.text


def test_request_id_is_propagated_or_generated(client: TestClient) -> None:
    echoed = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["X-Request-ID"] == "abc-123"
    generated = client.get("/health", headers={"X-Request-ID": "bad id\nwith newline"})
    assert generated.headers["X-Request-ID"] != "bad id\nwith newline"
    assert len(generated.headers["X-Request-ID"]) == 32


def test_research_endpoint_is_rate_limited(sample_info: dict[str, Any]) -> None:
    from finpilot.core.rate_limit import RateLimiter

    container = make_container(
        FakeProvider(sample_info), FakeGenerator(), research_limiter=RateLimiter(2, 60)
    )
    with TestClient(create_app(container)) as c:
        assert c.post("/v1/research", json={"ticker": "EXMP"}).status_code == 200
        assert c.post("/v1/research", json={"ticker": "EXMP"}).status_code == 200
        blocked = c.post("/v1/research", json={"ticker": "EXMP"})
        _assert_error(blocked, 429, "RATE_LIMITED")
        assert int(blocked.headers["Retry-After"]) >= 1
        assert c.get("/v1/companies/EXMP").status_code == 200  # separate default limiter
        assert c.get("/health").status_code == 200


def test_default_limiter_covers_read_endpoints_but_not_health(
    sample_info: dict[str, Any],
) -> None:
    from finpilot.core.rate_limit import RateLimiter

    container = make_container(
        FakeProvider(sample_info), FakeGenerator(), default_limiter=RateLimiter(1, 60)
    )
    with TestClient(create_app(container)) as c:
        assert c.get("/v1/companies/EXMP").status_code == 200
        _assert_error(c.get("/v1/companies/EXMP/scores"), 429, "RATE_LIMITED")
        assert all(c.get("/health").status_code == 200 for _ in range(5))
