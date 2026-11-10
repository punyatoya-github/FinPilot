"""App factory. Run with: uvicorn finpilot.main:create_app --factory"""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse

from finpilot import __version__
from finpilot.api.errors import register_error_handlers
from finpilot.api.routes import router
from finpilot.core.config import Settings
from finpilot.core.container import Container, build_container
from finpilot.core.logging import configure_logging

logger = logging.getLogger("finpilot.http")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def create_app(container: Container | None = None, *, mount_ui: bool | None = None) -> FastAPI:
    if container is None:
        settings = Settings()
        configure_logging(settings.log_level)
        container = build_container(settings)

    app = FastAPI(title="FinPilot", version=__version__)
    app.state.container = container

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _REQUEST_ID_RE.fullmatch(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %d (%.0f ms) request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
            request_id,
        )
        return response

    register_error_handlers(app)
    app.include_router(router)

    if container.settings.enable_ui if mount_ui is None else mount_ui:
        _mount_dashboard(app, container)
    return app


def _mount_dashboard(app: FastAPI, container: Container) -> None:
    import gradio as gr  # lazy: keeps API-only imports and tests light

    from finpilot.ui.backends import ServiceBackend
    from finpilot.ui.dashboard import build_dashboard

    dashboard = build_dashboard(
        ServiceBackend(container.research_service), container.research_limiter
    )
    gr.mount_gradio_app(app, dashboard, path="/ui")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/ui")
