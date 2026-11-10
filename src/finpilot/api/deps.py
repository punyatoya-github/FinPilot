from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from finpilot.core.container import Container
from finpilot.core.errors import RateLimitedError
from finpilot.core.rate_limit import RateLimiter
from finpilot.research.service import ResearchService


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


def get_research_service(
    container: Annotated[Container, Depends(get_container)],
) -> ResearchService:
    return container.research_service


ServiceDep = Annotated[ResearchService, Depends(get_research_service)]
ContainerDep = Annotated[Container, Depends(get_container)]


def client_key(request: Request, *, trust_proxy: bool) -> str:
    """Identify the caller. X-Forwarded-For is honored only when explicitly trusted."""
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce(limiter: RateLimiter, request: Request, container: Container) -> None:
    key = client_key(request, trust_proxy=container.settings.rate_limit_trust_proxy)
    retry_after = limiter.check(key)
    if retry_after > 0:
        raise RateLimitedError(retry_after)


def limit_default(request: Request, container: ContainerDep) -> None:
    _enforce(container.default_limiter, request, container)


def limit_research(request: Request, container: ContainerDep) -> None:
    _enforce(container.research_limiter, request, container)
