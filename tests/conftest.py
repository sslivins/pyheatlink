from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@dataclass
class Call:
    method: str
    path: str
    headers: dict[str, str]
    query: dict[str, str]
    json: Any


Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


@dataclass
class FakeHead:
    """A tiny stand-in for a head's HTTP server that records every call."""

    server: TestServer
    routes: dict[tuple[str, str], Any] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)

    @property
    def host(self) -> str:
        return f"127.0.0.1:{self.server.port}"

    def reply(
        self,
        method: str,
        path: str,
        payload: Any = None,
        *,
        status: int = 200,
        body: str | None = None,
    ) -> None:
        text = body if body is not None else json.dumps(payload)
        ctype = "application/json" if body is None else "text/plain"
        self.routes[(method, path)] = (status, text, ctype)

    def handle(self, method: str, path: str, handler: Handler) -> None:
        self.routes[(method, path)] = handler

    def last(self, method: str, path: str) -> Call:
        return [c for c in self.calls if c.method == method and c.path == path][-1]

    async def _dispatch(self, request: web.Request) -> web.StreamResponse:
        raw = await request.text()
        self.calls.append(
            Call(
                method=request.method,
                path=request.path,
                headers=dict(request.headers),
                query=dict(request.query),
                json=json.loads(raw) if raw else None,
            )
        )
        route = self.routes.get((request.method, request.path))
        if route is None:
            return web.Response(status=404, text="Nothing matches the given URI")
        if callable(route):
            return await route(request)
        status, text, ctype = route
        return web.Response(status=status, text=text, content_type=ctype)


async def _start_head() -> FakeHead:
    app = web.Application()
    head = FakeHead(server=TestServer(app))
    app.router.add_route("*", "/{tail:.*}", head._dispatch)
    await head.server.start_server()
    return head


@pytest.fixture
async def head() -> AsyncIterator[FakeHead]:
    h = await _start_head()
    yield h
    await h.server.close()


@pytest.fixture
async def peer() -> AsyncIterator[FakeHead]:
    h = await _start_head()
    yield h
    await h.server.close()


@pytest.fixture
async def session() -> AsyncIterator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as s:
        yield s
