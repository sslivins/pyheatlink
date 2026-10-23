"""Async HTTP client for one HeatLink head."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from types import TracebackType
from typing import Any, Self

import aiohttp

from .const import (
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DIAG_COUNTERS,
    REMOTE_TEMP_TTL_DEFAULT,
    REMOTE_TEMP_TTL_MAX,
    REMOTE_TEMP_TTL_MIN,
)
from .errors import (
    HeatLinkAuthError,
    HeatLinkConflictError,
    HeatLinkConnectionError,
    HeatLinkNotFoundError,
    HeatLinkRateLimitError,
    HeatLinkResponseError,
    HeatLinkScopeError,
    HeatLinkUnsupportedError,
)
from .models import (
    Capabilities,
    EventLog,
    Group,
    HouseSummary,
    Info,
    OtaStatus,
    ParkConfig,
    RemoteTempLease,
    Sensors,
    Settings,
    Status,
    Tandem,
    Ticket,
    TokenGrant,
    UpdateInfo,
)

_STATUS_ERRORS: dict[int, type[HeatLinkResponseError]] = {
    401: HeatLinkAuthError,
    403: HeatLinkScopeError,
    404: HeatLinkNotFoundError,
    409: HeatLinkConflictError,
    429: HeatLinkRateLimitError,
}


def _base_url(host: str, port: int) -> str:
    host = host.strip().rstrip("/")
    if "://" in host:
        return host
    if ":" in host and not host.startswith("["):
        if host.count(":") > 1:
            host = f"[{host}]"
        else:
            return f"http://{host}"
    return f"http://{host}" if port == DEFAULT_PORT else f"http://{host}:{port}"


def _drop_none(**kwargs: Any) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


class HeatLinkClient:
    """Talks to one head over its local HTTP API.

    Calls on one client never overlap (the firmware's HTTP server is small),
    and each has a hard timeout. Pass a shared ``aiohttp.ClientSession``
    (Home Assistant's, for instance); otherwise the client makes its own and
    closes it in :meth:`close`.
    """

    def __init__(
        self,
        host: str,
        session: aiohttp.ClientSession | None = None,
        *,
        token: str | None = None,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.host = host
        self.token = token
        self._base = _base_url(host, port)
        self._session = session
        self._own_session = session is None
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._own_session and self._session is not None:
            await self._session.close()
            self._session = None

    @property
    def base_url(self) -> str:
        return self._base

    # ── transport ──────────────────────────────────────────────────────

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        auth: bool = True,
    ) -> Any:
        """Send one request and return the decoded JSON body (or ``None``)."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        headers = {"Accept": "application/json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        url = f"{self._base}{path}"
        async with self._lock:
            try:
                async with self._session.request(
                    method,
                    url,
                    json=dict(body) if body is not None else None,
                    params=dict(params) if params else None,
                    headers=headers,
                    timeout=self._timeout,
                ) as resp:
                    text = await resp.text()
                    status = resp.status
            except TimeoutError as err:
                raise HeatLinkConnectionError(f"Timed out talking to {self.host}") from err
            except aiohttp.ClientError as err:
                raise HeatLinkConnectionError(f"Can't reach {self.host}: {err}") from err

        if status >= 400:
            raise _STATUS_ERRORS.get(status, HeatLinkResponseError)(status, _error_message(text))
        if not text.strip():
            return None
        try:
            return json.loads(text)
        except ValueError as err:
            raise HeatLinkConnectionError(f"Unreadable reply from {self.host}") from err

    async def _get(self, path: str, **kw: Any) -> dict[str, Any]:
        return _obj(await self.request("GET", path, **kw))

    async def _post(self, path: str, body: Mapping[str, Any] | None = None, **kw: Any) -> Any:
        return await self.request("POST", path, body=body if body is not None else {}, **kw)

    # ── identity (no auth) ─────────────────────────────────────────────

    async def get_info(self) -> Info:
        """Identity, auth state and feature flags. Needs no token.

        Raises :class:`HeatLinkUnsupportedError` for firmware older than 1.5,
        which has no ``/api/info``.
        """
        try:
            return Info.from_dict(await self._get("/api/info", auth=False))
        except HeatLinkNotFoundError as err:
            raise HeatLinkUnsupportedError(
                f"{self.host} runs firmware without /api/info (needs 1.5 or newer)"
            ) from err

    async def get_house_summary(self) -> HouseSummary:
        return HouseSummary.from_dict(await self._get("/api/house/summary", auth=False))

    # ── reads ──────────────────────────────────────────────────────────

    async def get_settings(self) -> Settings:
        return Settings.from_dict(await self._get("/api/settings"))

    async def get_status(self) -> Status:
        return Status.from_dict(await self._get("/api/status"))

    async def get_capabilities(self) -> Capabilities:
        return Capabilities.from_dict(await self._get("/api/capabilities"))

    async def get_park(self) -> ParkConfig:
        return ParkConfig.from_dict(await self._get("/api/park"))

    async def get_group(self) -> Group:
        return Group.from_dict(await self._get("/api/group"))

    async def get_sensors(self) -> Sensors:
        return Sensors.from_dict(await self._get("/api/sensors"))

    async def get_events(self, since: int = 0, limit: int = 100) -> EventLog:
        return EventLog.from_dict(
            await self._get("/api/events", params={"since": since, "limit": limit})
        )

    async def get_update(self) -> UpdateInfo:
        return UpdateInfo.from_dict(await self._get("/api/update"))

    async def get_ota_status(self) -> OtaStatus:
        return OtaStatus.from_dict(await self._get("/api/ota/status"))

    # ── control (control scope) ────────────────────────────────────────

    async def set_climate(
        self,
        *,
        power: bool | None = None,
        mode: str | None = None,
        temperature: float | None = None,
        fan: str | None = None,
        vane: str | None = None,
        wide_vane: str | None = None,
        heat_to: float | None = None,
        cool_to: float | None = None,
    ) -> None:
        """Change any mix of climate settings in one call.

        Setting ``mode`` also turns the head on unless ``power=False`` is
        passed with it, in which case the mode is stored and the head stays
        off. ``heat_to``/``cool_to`` set the Auto range (Tandem on); the
        firmware keeps them at least 2 °C apart and applies them before
        ``mode``.
        """
        body = _drop_none(
            mode=mode.upper() if mode is not None else None,
            power=None if power is None else ("ON" if power else "OFF"),
            temperature=temperature,
            heat_to=heat_to,
            cool_to=cool_to,
            fan=fan.upper() if fan is not None else None,
            vane=vane.upper() if vane is not None else None,
            wideVane=wide_vane,
        )
        if not body:
            raise ValueError("set_climate needs at least one setting")
        await self._post("/api/settings", body)

    async def turn_on(self) -> None:
        await self.set_climate(power=True)

    async def turn_off(self) -> None:
        await self.set_climate(power=False)

    async def set_remote_temp(
        self, temp: float, ttl_s: int = REMOTE_TEMP_TTL_DEFAULT
    ) -> RemoteTempLease:
        """Feed the unit a room temperature (°C) from an outside sensor.

        The head uses it until ``ttl_s`` runs out, so send it again before
        then to keep the feed going. Raises :class:`HeatLinkConflictError`
        while a paired room sensor is feeding the head.
        """
        if not REMOTE_TEMP_TTL_MIN <= ttl_s <= REMOTE_TEMP_TTL_MAX:
            raise ValueError(f"ttl_s must be {REMOTE_TEMP_TTL_MIN}-{REMOTE_TEMP_TTL_MAX}")
        return RemoteTempLease.from_dict(
            _obj(await self._post("/api/remote-temp", {"temp": temp, "ttl_s": ttl_s}))
        )

    async def clear_remote_temp(self) -> RemoteTempLease:
        """End the remote temperature feed now."""
        return RemoteTempLease.from_dict(_obj(await self._post("/api/remote-temp", {"temp": None})))

    # ── admin ──────────────────────────────────────────────────────────

    async def set_park(
        self,
        *,
        enabled: bool | None = None,
        delta_c: float | None = None,
        min_off_s: int | None = None,
        probe_enabled: bool | None = None,
        probe_interval_s: int | None = None,
        probe_duration_s: int | None = None,
    ) -> ParkConfig:
        """Change off-at-setpoint settings. Returns the applied config."""
        body = _drop_none(
            enabled=enabled,
            delta_c=delta_c,
            min_off_s=min_off_s,
            probe_enabled=probe_enabled,
            probe_interval_s=probe_interval_s,
            probe_duration_s=probe_duration_s,
        )
        if not body:
            raise ValueError("set_park needs at least one setting")
        return ParkConfig.from_dict(_obj(await self._post("/api/park", body)))

    async def set_tandem(
        self,
        *,
        enabled: bool | None = None,
        min_slice_s: int | None = None,
        max_slice_s: int | None = None,
        settle_s: int | None = None,
    ) -> Tandem:
        """Change Tandem (heat/cool time-slicing) for the whole outdoor unit."""
        body = _drop_none(
            enabled=enabled, min_slice_s=min_slice_s, max_slice_s=max_slice_s, settle_s=settle_s
        )
        if not body:
            raise ValueError("set_tandem needs at least one setting")
        return Tandem.from_dict(_obj(await self._post("/api/group/slice", body)))

    async def install_update(self) -> None:
        """Start installing the latest firmware. Watch :meth:`get_ota_status`."""
        await self._post("/api/update/install")

    async def restart(self) -> None:
        await self._post("/api/system/restart")

    async def reset_diag(self, counter: str) -> None:
        """Reset a diagnostic counter: ``brownout``, ``wifi-drops`` or ``vin-min``."""
        if counter not in DIAG_COUNTERS:
            raise ValueError(f"counter must be one of {', '.join(DIAG_COUNTERS)}")
        await self._post(f"/api/diag/reset-{counter}")

    # ── token tickets ──────────────────────────────────────────────────

    async def request_ticket(self, uid: str) -> Ticket:
        """Ask this head for a ticket that mints a token on group peer ``uid``.

        Needs an integration token; the new token gets the same scope.
        """
        return Ticket.from_dict(_obj(await self._post("/api/tokens/ticket", {"uid": uid})))

    async def redeem_ticket(self, ticket: Ticket) -> TokenGrant:
        """Turn a ticket from a peer into a token on this head. Needs no auth."""
        return TokenGrant.from_dict(
            _obj(
                await self._post(
                    "/api/tokens/redeem",
                    {"ticket": ticket.ticket, "label": ticket.label},
                    auth=False,
                )
            )
        )

    async def create_peer_token(self, peer_host: str, uid: str) -> TokenGrant:
        """Mint a token on group peer ``uid`` at ``peer_host`` using this head's token."""
        ticket = await self.request_ticket(uid)
        peer = HeatLinkClient(
            peer_host,
            self._session,
            timeout=self._timeout.total or DEFAULT_TIMEOUT,
        )
        return await peer.redeem_ticket(ticket)


def _obj(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    raise HeatLinkConnectionError("Expected a JSON object in the reply")


def _error_message(text: str) -> str:
    try:
        data = json.loads(text)
    except ValueError:
        return text.strip()[:200]
    if isinstance(data, dict) and isinstance(data.get("error"), str):
        return str(data["error"])
    return text.strip()[:200]
