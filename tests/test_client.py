from __future__ import annotations

import asyncio

import aiohttp
import pytest
from aiohttp import web

from pyheatlink import (
    HeatLinkAuthError,
    HeatLinkClient,
    HeatLinkConflictError,
    HeatLinkConnectionError,
    HeatLinkRateLimitError,
    HeatLinkResponseError,
    HeatLinkScopeError,
    HeatLinkUnsupportedError,
)
from pyheatlink.client import _base_url

from .conftest import FakeHead, load


@pytest.fixture
def client(head: FakeHead, session: aiohttp.ClientSession) -> HeatLinkClient:
    return HeatLinkClient(head.host, session, token="tok123", timeout=2)


@pytest.mark.parametrize(
    ("method", "path", "fixture_name", "attr"),
    [
        ("get_settings", "/api/settings", "settings", "mode"),
        ("get_status", "/api/status", "status", "version"),
        ("get_capabilities", "/api/capabilities", "capabilities", "unit_on"),
        ("get_park", "/api/park", "park", "delta_c"),
        ("get_group", "/api/group", "group", "label"),
        ("get_sensors", "/api/sensors", "sensors", "max"),
        ("get_update", "/api/update", "update", "latest"),
        ("get_ota_status", "/api/ota/status", "ota_status", "state"),
    ],
)
async def test_reads_send_bearer(
    client: HeatLinkClient, head: FakeHead, method: str, path: str, fixture_name: str, attr: str
) -> None:
    head.reply("GET", path, load(fixture_name))
    result = await getattr(client, method)()
    assert getattr(result, attr) is not None
    assert head.last("GET", path).headers["Authorization"] == "Bearer tok123"


async def test_public_reads_skip_auth(client: HeatLinkClient, head: FakeHead) -> None:
    head.reply("GET", "/api/info", load("info"))
    head.reply("GET", "/api/house/summary", load("house_summary"))
    assert (await client.get_info()).uid == "6dac"
    assert (await client.get_house_summary()).uid == "6dac"
    for path in ("/api/info", "/api/house/summary"):
        assert "Authorization" not in head.last("GET", path).headers


async def test_old_firmware_is_unsupported(client: HeatLinkClient) -> None:
    with pytest.raises(HeatLinkUnsupportedError):
        await client.get_info()


async def test_events_params(client: HeatLinkClient, head: FakeHead) -> None:
    head.reply("GET", "/api/events", load("events"))
    log = await client.get_events(since=630, limit=5)
    assert log.seq == 641
    assert head.last("GET", "/api/events").query == {"since": "630", "limit": "5"}


async def test_set_climate_body(client: HeatLinkClient, head: FakeHead) -> None:
    head.reply("POST", "/api/settings", {"status": "ok"})
    await client.set_climate(power=False, mode="cool", temperature=21.5, fan="quiet")
    assert head.last("POST", "/api/settings").json == {
        "mode": "COOL",
        "power": "OFF",
        "temperature": 21.5,
        "fan": "QUIET",
    }
    await client.turn_on()
    assert head.last("POST", "/api/settings").json == {"power": "ON"}
    await client.turn_off()
    assert head.last("POST", "/api/settings").json == {"power": "OFF"}
    await client.set_climate(vane="swing", wide_vane="<>")
    assert head.last("POST", "/api/settings").json == {"vane": "SWING", "wideVane": "<>"}
    await client.set_climate(mode="auto", heat_to=19.5, cool_to=23)
    assert head.last("POST", "/api/settings").json == {
        "mode": "AUTO",
        "heat_to": 19.5,
        "cool_to": 23,
    }
    with pytest.raises(ValueError):
        await client.set_climate()


async def test_remote_temp(client: HeatLinkClient, head: FakeHead) -> None:
    head.reply("POST", "/api/remote-temp", {"active": True, "temp": 21.2, "expires_in_s": 600})
    lease = await client.set_remote_temp(21.2)
    assert lease.active and lease.expires_in_s == 600
    assert head.last("POST", "/api/remote-temp").json == {"temp": 21.2, "ttl_s": 600}

    head.reply("POST", "/api/remote-temp", {"active": False})
    assert not (await client.clear_remote_temp()).active
    assert head.last("POST", "/api/remote-temp").json == {"temp": None}

    with pytest.raises(ValueError):
        await client.set_remote_temp(20, ttl_s=30)


async def test_remote_temp_conflict(client: HeatLinkClient, head: FakeHead) -> None:
    head.reply(
        "POST", "/api/remote-temp", {"error": "A room sensor is feeding this head"}, status=409
    )
    with pytest.raises(HeatLinkConflictError) as exc:
        await client.set_remote_temp(20)
    assert exc.value.status == 409
    assert exc.value.message == "A room sensor is feeding this head"


async def test_admin_writes(client: HeatLinkClient, head: FakeHead) -> None:
    head.reply("POST", "/api/park", load("park"))
    park = await client.set_park(enabled=True, delta_c=0.5)
    assert park.enabled
    assert head.last("POST", "/api/park").json == {"enabled": True, "delta_c": 0.5}

    head.reply("POST", "/api/group/slice", load("group")["slice"])
    tandem = await client.set_tandem(min_slice_s=300)
    assert tandem.min_slice_s == 300
    assert head.last("POST", "/api/group/slice").json == {"min_slice_s": 300}

    for path in ("/api/update/install", "/api/system/restart", "/api/diag/reset-vin-min"):
        head.reply("POST", path, {"status": "ok"})
    await client.install_update()
    await client.restart()
    await client.reset_diag("vin-min")
    assert head.last("POST", "/api/system/restart").json == {}
    assert head.last("POST", "/api/diag/reset-vin-min")

    for bad in (client.set_park(), client.set_tandem(), client.reset_diag("everything")):
        with pytest.raises(ValueError):
            await bad


async def test_peer_token(client: HeatLinkClient, head: FakeHead, peer: FakeHead) -> None:
    head.reply(
        "POST",
        "/api/tokens/ticket",
        {"ticket": "TKT", "label": "HA", "scope": "control", "expires": 1792700000},
    )
    peer.reply(
        "POST",
        "/api/tokens/redeem",
        {"token": "newtok", "id": "abcd1234", "label": "HA", "scope": "control"},
        status=201,
    )
    grant = await client.create_peer_token(peer.host, "e6ec")
    assert grant.token == "newtok" and grant.scope == "control"
    assert head.last("POST", "/api/tokens/ticket").json == {"uid": "e6ec"}
    redeem = peer.last("POST", "/api/tokens/redeem")
    assert redeem.json == {"ticket": "TKT", "label": "HA"}
    assert "Authorization" not in redeem.headers


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, HeatLinkAuthError),
        (403, HeatLinkScopeError),
        (409, HeatLinkConflictError),
        (429, HeatLinkRateLimitError),
        (500, HeatLinkResponseError),
    ],
)
async def test_status_errors(
    client: HeatLinkClient, head: FakeHead, status: int, error: type[Exception]
) -> None:
    head.reply("GET", "/api/settings", status=status, body="Nope")
    with pytest.raises(error) as exc:
        await client.get_settings()
    assert str(exc.value) == f"HTTP {status}: Nope"


async def test_bad_replies(client: HeatLinkClient, head: FakeHead) -> None:
    for body, match in (("<html>", "Unreadable"), ("[1, 2]", "JSON object"), ("", "JSON object")):
        head.reply("GET", "/api/settings", body=body)
        with pytest.raises(HeatLinkConnectionError, match=match):
            await client.get_settings()


async def test_dropped_connection(client: HeatLinkClient, head: FakeHead) -> None:
    async def hang_up(request: web.Request) -> web.Response:
        assert request.transport is not None
        request.transport.close()
        return web.Response()

    head.handle("GET", "/api/settings", hang_up)
    with pytest.raises(HeatLinkConnectionError, match="Can't reach"):
        await client.get_settings()


async def test_timeout(head: FakeHead, session: aiohttp.ClientSession) -> None:
    async def stall(request: web.Request) -> web.Response:
        await asyncio.sleep(2)
        return web.json_response({})

    head.handle("GET", "/api/settings", stall)
    client = HeatLinkClient(head.host, session, timeout=0.2)
    with pytest.raises(HeatLinkConnectionError, match="Timed out"):
        await client.get_settings()


async def test_requests_never_overlap(client: HeatLinkClient, head: FakeHead) -> None:
    in_flight = 0
    peak = 0

    async def slow(request: web.Request) -> web.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return web.json_response(load("ota_status"))

    head.handle("GET", "/api/ota/status", slow)
    await asyncio.gather(*(client.get_ota_status() for _ in range(5)))
    assert peak == 1


async def test_owns_session_when_none_given(head: FakeHead) -> None:
    head.reply("GET", "/api/ota/status", load("ota_status"))
    async with HeatLinkClient(head.host) as client:
        assert (await client.get_ota_status()).state == "idle"
        session = client._session
    assert session is not None and session.closed


async def test_shared_session_is_left_open(session: aiohttp.ClientSession) -> None:
    async with HeatLinkClient("h", session) as client:
        assert client.base_url == "http://h"
    assert not session.closed


@pytest.mark.parametrize(
    ("host", "port", "url"),
    [
        ("192.168.1.151", 80, "http://192.168.1.151"),
        ("heatlink-6dac.local", 8080, "http://heatlink-6dac.local:8080"),
        ("192.168.1.151:81", 80, "http://192.168.1.151:81"),
        ("http://example/", 80, "http://example"),
        ("fe80::1", 80, "http://[fe80::1]"),
    ],
)
def test_base_url(host: str, port: int, url: str) -> None:
    assert _base_url(host, port) == url
