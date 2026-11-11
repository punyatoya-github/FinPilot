import importlib
import sys
from typing import Any

import pytest
from fastapi import FastAPI

from finpilot.__main__ import main


def test_main_passes_options_to_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr("uvicorn.run", lambda *a, **kw: calls.append((a, kw)))
    assert main(["--port", "9100", "--reload"]) == 0
    assert calls == [(("finpilot.asgi:app",), {"host": "127.0.0.1", "port": 9100, "reload": True})]


def test_main_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("uvicorn.run", lambda *a, **kw: calls.append(kw))
    main([])
    assert calls == [{"host": "127.0.0.1", "port": 8000, "reload": False}]


def test_asgi_module_exposes_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINPILOT_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("FINPILOT_ENABLE_UI", "false")
    monkeypatch.delitem(sys.modules, "finpilot.asgi", raising=False)
    module = importlib.import_module("finpilot.asgi")
    try:
        assert isinstance(module.app, FastAPI)
    finally:
        sys.modules.pop("finpilot.asgi", None)
