"""Maps domain exceptions to the uniform error envelope {"error": {code, message, request_id}}."""

from __future__ import annotations

import logging
import math

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from finpilot.core import errors as e

logger = logging.getLogger(__name__)

ERROR_MAPPING: list[tuple[type[e.FinPilotError], int, str]] = [
    (e.InvalidTickerError, 400, "INVALID_TICKER"),
    (e.TickerNotFoundError, 404, "TICKER_NOT_FOUND"),
    (e.ReportNotFoundError, 404, "REPORT_NOT_FOUND"),
    (e.InsufficientDataError, 422, "INSUFFICIENT_DATA"),
    (e.RateLimitedError, 429, "RATE_LIMITED"),
    (e.DataProviderError, 502, "DATA_PROVIDER_ERROR"),
    (e.LLMError, 502, "LLM_ERROR"),
]


def classify(exc: BaseException) -> tuple[int, str]:
    """(HTTP status, machine-readable code) for an exception."""
    for cls, status, code in ERROR_MAPPING:
        if isinstance(exc, cls):
            return status, code
    return 500, "INTERNAL_ERROR"


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def _envelope(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": _request_id(request)}},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(e.FinPilotError)
    async def _domain_error(request: Request, exc: Exception) -> JSONResponse:
        status, code = classify(exc)
        if status == 500:
            logger.exception("unmapped domain error")
            return _envelope(request, 500, code, "Internal server error")
        response = _envelope(request, status, code, str(exc))
        if isinstance(exc, e.RateLimitedError):
            response.headers["Retry-After"] = str(max(1, math.ceil(exc.retry_after)))
        return response

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, RequestValidationError)
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()))
        message = f"{where}: {first.get('msg', 'invalid')}"
        return _envelope(request, 422, "VALIDATION_ERROR", message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return _envelope(request, 500, "INTERNAL_ERROR", "Internal server error")
