from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from finpilot.core.container import Container
from finpilot.research.service import ResearchService


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


def get_research_service(
    container: Annotated[Container, Depends(get_container)],
) -> ResearchService:
    return container.research_service


ServiceDep = Annotated[ResearchService, Depends(get_research_service)]
ContainerDep = Annotated[Container, Depends(get_container)]
