# pyheatlink

Async Python client for [HeatLink](https://github.com/sslivins/heatlink), the
local Wi-Fi controller for Mitsubishi mini-split heads (CN105). It talks to each
head's HTTP API on your LAN, with no cloud involved. The
[Home Assistant integration](https://github.com/sslivins/hass-heatlink) is built on it.

Needs HeatLink firmware 1.5 or newer (the first version with `/api/info`).

## Install

```bash
pip install pyheatlink
```

## Usage

```python
import asyncio
import aiohttp
from pyheatlink import HeatLinkClient, Feature

async def main() -> None:
    async with aiohttp.ClientSession() as session:
        head = HeatLinkClient("192.168.1.151", session, token="hlt1_...")

        info = await head.get_info()            # public, no token needed
        print(info.name, info.fw, info.group)

        s = await head.get_settings()
        print(s.power, s.mode, s.temperature, s.room_temperature)

        await head.set_climate(mode="heat", temperature=21)

        if info.has(Feature.REMOTE_TEMP):
            await head.set_remote_temp(20.5, ttl_s=600)   # resend before it expires

asyncio.run(main())
```

### Tokens

Create an integration token in the head's web UI (**Settings → API Access → Integration tokens**)
with the scope you need:

| Scope     | Allows |
|-----------|--------|
| `read`    | every read |
| `control` | climate changes and the remote temperature feed |
| `admin`   | off-at-setpoint, Tandem, updates, restart, diagnostics |

Heads sharing an outdoor unit can mint tokens for each other, so one token is
enough to set up the whole group:

```python
group = await head.get_group()
for peer in group.members:
    grant = await head.create_peer_token(peer.ip, peer.uid)
    print(peer.name, grant.token)   # same scope as `head`'s token
```

### Discovery

Heads advertise `_mmhvac._tcp.local.` over mDNS with their `uid` in the TXT
record (`pyheatlink.const.ZEROCONF_TYPE`).

## API

| Method | Endpoint | Scope |
|--------|----------|-------|
| `get_info()` | `GET /api/info` | none |
| `get_house_summary()` | `GET /api/house/summary` | none |
| `get_settings()` | `GET /api/settings` | read |
| `get_status()` | `GET /api/status` | read |
| `get_capabilities()` | `GET /api/capabilities` | read |
| `get_park()` | `GET /api/park` | read |
| `get_group()` | `GET /api/group` (includes Tandem) | read |
| `get_sensors()` | `GET /api/sensors` | read |
| `get_events(since, limit)` | `GET /api/events` | read |
| `get_update()` / `get_ota_status()` | `GET /api/update`, `/api/ota/status` | read |
| `set_climate(power, mode, temperature, fan, vane, wide_vane)` | `POST /api/settings` | control |
| `set_remote_temp(temp, ttl_s)` / `clear_remote_temp()` | `POST /api/remote-temp` | control |
| `set_park(...)` | `POST /api/park` | admin |
| `set_tandem(...)` | `POST /api/group/slice` | admin |
| `install_update()`, `restart()`, `reset_diag(counter)` | | admin |
| `request_ticket(uid)`, `redeem_ticket(ticket)`, `create_peer_token(host, uid)` | `/api/tokens/*` | token |

All models are frozen dataclasses that tolerate missing or unknown fields; the
full payload is kept in `.raw`.

Errors all derive from `HeatLinkError`:

| Exception | When |
|-----------|------|
| `HeatLinkConnectionError` | unreachable, timed out, or unreadable reply |
| `HeatLinkAuthError` | 401: missing, wrong or revoked token |
| `HeatLinkScopeError` | 403: token scope too low |
| `HeatLinkConflictError` | 409: refused in the current state (e.g. a room sensor owns the temperature) |
| `HeatLinkRateLimitError` | 429: locked out after failed attempts |
| `HeatLinkUnsupportedError` | firmware older than 1.5 |
| `HeatLinkResponseError` | any other HTTP error (`.status`, `.message`) |

Calls on one client never overlap, and each has a timeout (default 10 s).

## Command line

```bash
pyheatlink 192.168.1.151 info
pyheatlink 192.168.1.151 --token hlt1_... set --mode heat --temp 21
pyheatlink 192.168.1.151 remote-temp 20.5 --ttl 600
pyheatlink 192.168.1.151 remote-temp clear
```

`HEATLINK_TOKEN` in the environment works too.

## Development

```bash
pip install -e .[tests]
ruff check src tests && ruff format --check src tests
mypy src/pyheatlink
pytest --cov=src/pyheatlink
```

Tests run against a local fake head serving responses captured from real
firmware (`tests/fixtures`).

Releases are automatic: merging to `main` publishes the version in
`pyproject.toml` to PyPI and bumps the patch version.
