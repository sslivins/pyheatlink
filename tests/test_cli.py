from __future__ import annotations

import asyncio
import json

import pytest

from pyheatlink.__main__ import main

from .conftest import FakeHead, load


async def run(*argv: str) -> int:
    # main() runs its own event loop, so keep it off the loop serving the fake head.
    return await asyncio.to_thread(main, list(argv))


async def test_read_command(head: FakeHead, capsys: pytest.CaptureFixture[str]) -> None:
    head.reply("GET", "/api/info", load("info"))
    assert await run(head.host, "info") == 0
    assert json.loads(capsys.readouterr().out)["uid"] == "6dac"


async def test_set_command(head: FakeHead, capsys: pytest.CaptureFixture[str]) -> None:
    head.reply("POST", "/api/settings", {"status": "ok"})
    head.reply("GET", "/api/settings", load("settings"))
    assert await run(head.host, "--token", "t", "set", "--power", "off", "--mode", "cool") == 0
    assert head.last("POST", "/api/settings").json == {"mode": "COOL", "power": "OFF"}
    assert head.last("POST", "/api/settings").headers["Authorization"] == "Bearer t"
    assert json.loads(capsys.readouterr().out)["mode"] == "COOL"


async def test_remote_temp_command(head: FakeHead, capsys: pytest.CaptureFixture[str]) -> None:
    head.reply("POST", "/api/remote-temp", {"active": True, "temp": 20.0})
    assert await run(head.host, "remote-temp", "20", "--ttl", "120") == 0
    assert head.last("POST", "/api/remote-temp").json == {"temp": 20.0, "ttl_s": 120}
    assert json.loads(capsys.readouterr().out)["active"] is True
    head.reply("POST", "/api/remote-temp", {"active": False})
    assert await run(head.host, "remote-temp", "clear") == 0
    assert json.loads(capsys.readouterr().out)["active"] is False


async def test_error_exit(head: FakeHead, capsys: pytest.CaptureFixture[str]) -> None:
    head.reply("GET", "/api/settings", status=401, body="Unauthorized")
    assert await run(head.host, "settings") == 1
    assert "401" in capsys.readouterr().err
