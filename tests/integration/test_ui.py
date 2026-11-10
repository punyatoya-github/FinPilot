from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient

from finpilot.core.errors import DataProviderError, TickerNotFoundError
from finpilot.core.rate_limit import RateLimiter
from finpilot.main import create_app
from finpilot.ui.backends import BackendError, HttpBackend, ServiceBackend

from ..fakes import FakeGenerator, FakeProvider, make_container


def test_service_backend_success_and_error_codes(sample_info: dict[str, Any]) -> None:
    service = make_container(FakeProvider(sample_info), FakeGenerator()).research_service
    backend = ServiceBackend(service)
    company, scores = backend.company_scores("EXMP")
    assert company.profile.name == "Example Corp" and scores.overall > 0
    assert backend.research("EXMP").report is not None

    with pytest.raises(BackendError) as bad:
        backend.company_scores("not valid!")
    assert bad.value.code == "INVALID_TICKER"

    missing = ServiceBackend(
        make_container(
            FakeProvider(error=TickerNotFoundError("ZZZZ")), FakeGenerator()
        ).research_service
    )
    with pytest.raises(BackendError) as nf:
        missing.research("ZZZZ")
    assert nf.value.code == "TICKER_NOT_FOUND"


def test_http_backend_against_real_api_stack(sample_info: dict[str, Any]) -> None:
    app = create_app(make_container(FakeProvider(sample_info), FakeGenerator()))
    with TestClient(app) as client:
        backend = HttpBackend("http://testserver", client=cast(httpx.Client, client))
        company, scores = backend.company_scores("exmp")
        assert company.profile.ticker == "EXMP" and 0 <= scores.overall <= 100
        result = backend.research("EXMP", refresh=False)
        assert result.report is not None and result.company.name == "Example Corp"
        with pytest.raises(BackendError) as exc:
            backend.company_scores("bad;ticker")
        assert exc.value.code == "INVALID_TICKER"


def test_http_backend_maps_provider_and_rate_limit_errors(sample_info: dict[str, Any]) -> None:
    app = create_app(
        make_container(
            FakeProvider(error=DataProviderError("down")),
            FakeGenerator(),
            default_limiter=RateLimiter(1, 60),
        )
    )
    with TestClient(app) as client:
        backend = HttpBackend("http://testserver", client=cast(httpx.Client, client))
        with pytest.raises(BackendError) as first:
            backend.company_scores("EXMP")
        assert first.value.code == "DATA_PROVIDER_ERROR"
        with pytest.raises(BackendError) as second:
            backend.company_scores("EXMP")
        assert second.value.code == "RATE_LIMITED"


def test_http_backend_unreachable_and_non_envelope_errors() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    down = HttpBackend(
        "http://x", client=httpx.Client(transport=httpx.MockTransport(refuse), base_url="http://x")
    )
    with pytest.raises(BackendError) as exc:
        down.research("EXMP")
    assert exc.value.code == "API_UNREACHABLE"

    html_500 = httpx.MockTransport(lambda r: httpx.Response(500, text="<html>oops</html>"))
    odd = HttpBackend("http://x", client=httpx.Client(transport=html_500, base_url="http://x"))
    with pytest.raises(BackendError) as exc2:
        odd.research("EXMP")
    assert exc2.value.code == "API_ERROR" and "500" in exc2.value.message


def test_dashboard_is_mounted_and_root_redirects(sample_info: dict[str, Any]) -> None:
    container = make_container(FakeProvider(sample_info), FakeGenerator())
    with TestClient(create_app(container, mount_ui=True)) as client:
        ui = client.get("/ui", follow_redirects=True)
        assert ui.status_code == 200 and "FinPilot" in ui.text
        root = client.get("/", follow_redirects=False)
        assert root.status_code in (302, 307) and root.headers["location"] == "/ui"
        assert client.get("/health").status_code == 200  # API unaffected by the mount


def test_ui_not_mounted_when_disabled(sample_info: dict[str, Any]) -> None:
    container = make_container(FakeProvider(sample_info), FakeGenerator())
    with TestClient(create_app(container)) as client:  # fake container sets enable_ui=False
        assert client.get("/ui").status_code == 404
