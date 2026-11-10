"""Backends the dashboard talks to: in-process service (mounted) or remote API (standalone)."""

from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import quote

import httpx

from finpilot.api.errors import classify
from finpilot.api.schemas import CompanyScoresResponse
from finpilot.core.errors import FinPilotError
from finpilot.domain.models import CompanyData, HealthScores, ResearchResult
from finpilot.research.service import ResearchService


class BackendError(Exception):
    """A user-presentable failure, carrying the API error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DashboardBackend(Protocol):
    def company_scores(self, ticker: str) -> tuple[CompanyData, HealthScores]: ...
    def research(self, ticker: str, refresh: bool = False) -> ResearchResult: ...


class ServiceBackend:
    """Calls the research service directly (no HTTP hop) when the UI is mounted in the API."""

    def __init__(self, service: ResearchService) -> None:
        self._service = service

    def company_scores(self, ticker: str) -> tuple[CompanyData, HealthScores]:
        try:
            return self._service.get_scores(ticker)
        except FinPilotError as exc:
            raise BackendError(classify(exc)[1], str(exc)) from exc

    def research(self, ticker: str, refresh: bool = False) -> ResearchResult:
        try:
            return self._service.research(ticker, refresh=refresh)
        except FinPilotError as exc:
            raise BackendError(classify(exc)[1], str(exc)) from exc


class HttpBackend:
    """Calls a remote FinPilot API. Pass `client` to reuse a configured httpx client."""

    def __init__(
        self, base_url: str, client: httpx.Client | None = None, timeout: float = 90.0
    ) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)

    def company_scores(self, ticker: str) -> tuple[CompanyData, HealthScores]:
        data = self._call("GET", f"/v1/companies/{quote(ticker, safe='')}/scores")
        parsed = CompanyScoresResponse.model_validate(data)
        return parsed.company, parsed.scores

    def research(self, ticker: str, refresh: bool = False) -> ResearchResult:
        data = self._call("POST", "/v1/research", json={"ticker": ticker, "refresh": refresh})
        return ResearchResult.model_validate(data)

    def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            message = f"Could not reach the FinPilot API: {exc}"
            raise BackendError("API_UNREACHABLE", message) from exc
        if response.is_success:
            return response.json()
        code, message = "API_ERROR", f"The API returned HTTP {response.status_code}."
        try:
            error = response.json()["error"]
            code, message = str(error["code"]), str(error["message"])
        except (ValueError, KeyError, TypeError):
            pass
        raise BackendError(code, message)
