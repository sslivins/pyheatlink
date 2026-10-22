"""Typed, read-only views of HeatLink API responses.

Every model is built with ``from_dict`` and tolerates missing or unexpected
fields: newer firmware may add keys and older firmware may omit them. The
original payload is kept in ``raw`` for anything not modelled here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .const import EventActor, EventCategory, Feature, Power

JSON = Mapping[str, Any]


def _map(v: Any) -> JSON:
    return v if isinstance(v, Mapping) else {}


def _str(d: JSON, key: str, default: str = "") -> str:
    v = d.get(key)
    return v if isinstance(v, str) else default


def _opt_str(d: JSON, key: str) -> str | None:
    v = d.get(key)
    return v if isinstance(v, str) else None


def _bool(d: JSON, key: str, default: bool = False) -> bool:
    v = d.get(key)
    return v if isinstance(v, bool) else default


def _opt_bool(d: JSON, key: str) -> bool | None:
    v = d.get(key)
    return v if isinstance(v, bool) else None


def _opt_float(d: JSON, key: str) -> float | None:
    v = d.get(key)
    if isinstance(v, bool) or not isinstance(v, int | float):
        return None
    return round(float(v), 2)


def _opt_int(d: JSON, key: str) -> int | None:
    v = d.get(key)
    if isinstance(v, bool) or not isinstance(v, int | float):
        return None
    return int(v)


def _int(d: JSON, key: str, default: int = 0) -> int:
    v = _opt_int(d, key)
    return default if v is None else v


def _list(d: JSON, key: str) -> list[Any]:
    v = d.get(key)
    return v if isinstance(v, list) else []


def _raw() -> Any:
    return field(default_factory=dict, repr=False, compare=False)


# ── /api/info ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AuthInfo:
    state: str
    web_login: bool
    open_climate: bool
    api_key: bool
    tokens: bool

    @classmethod
    def from_dict(cls, d: JSON) -> AuthInfo:
        return cls(
            state=_str(d, "state"),
            web_login=_bool(d, "web_login"),
            open_climate=_bool(d, "open_climate"),
            api_key=_bool(d, "api_key"),
            tokens=_bool(d, "tokens"),
        )


@dataclass(frozen=True)
class MqttInfo:
    configured: bool
    discovery: bool

    @classmethod
    def from_dict(cls, d: JSON) -> MqttInfo:
        return cls(configured=_bool(d, "configured"), discovery=_bool(d, "discovery", True))


@dataclass(frozen=True)
class GroupRef:
    """Stable identity of the outdoor unit a head belongs to."""

    ghash: str
    label: str

    @classmethod
    def from_dict(cls, d: JSON) -> GroupRef | None:
        ghash = _str(d, "ghash")
        return cls(ghash=ghash, label=_str(d, "label")) if ghash else None


@dataclass(frozen=True)
class Info:
    """Public identity and capabilities (``GET /api/info``, no auth needed)."""

    uid: str
    name: str
    hostname: str
    model: str
    fw: str
    api_version: int
    pv: int
    auth: AuthInfo
    features: frozenset[str]
    mqtt: MqttInfo | None
    group: GroupRef | None
    raw: JSON = _raw()

    @classmethod
    def from_dict(cls, d: JSON) -> Info:
        mqtt = d.get("mqtt")
        return cls(
            uid=_str(d, "uid"),
            name=_str(d, "name"),
            hostname=_str(d, "hostname"),
            model=_str(d, "model"),
            fw=_str(d, "fw"),
            api_version=_int(d, "api_version"),
            pv=_int(d, "pv"),
            auth=AuthInfo.from_dict(_map(d.get("auth"))),
            features=frozenset(f for f in _list(d, "features") if isinstance(f, str)),
            mqtt=MqttInfo.from_dict(mqtt) if isinstance(mqtt, Mapping) else None,
            group=GroupRef.from_dict(_map(d.get("group"))),
            raw=d,
        )

    def has(self, feature: Feature | str) -> bool:
        return str(feature) in self.features


# ── /api/settings ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParkStatus:
    """Live off-at-setpoint state."""

    enabled: bool
    state: str
    parked: bool
    reason: str
    unit_on: bool
    satisfied: bool
    held: bool
    forced: bool
    slicing: bool
    quiet_fan: bool
    room_sensor: bool
    next_probe_s: int | None

    @classmethod
    def from_dict(cls, d: JSON) -> ParkStatus:
        return cls(
            enabled=_bool(d, "enabled"),
            state=_str(d, "state"),
            parked=_bool(d, "parked"),
            reason=_str(d, "reason"),
            unit_on=_bool(d, "unit_on"),
            satisfied=_bool(d, "satisfied"),
            held=_bool(d, "held"),
            forced=_bool(d, "forced"),
            slicing=_bool(d, "slicing"),
            quiet_fan=_bool(d, "quiet_fan"),
            room_sensor=_bool(d, "room_sensor"),
            next_probe_s=_opt_int(d, "next_probe_s"),
        )


@dataclass(frozen=True)
class RoomSensorSummary:
    """The paired room sensors' combined reading, as used by the head."""

    state: str
    temp: float | None
    n_fresh: int

    @classmethod
    def from_dict(cls, d: JSON) -> RoomSensorSummary:
        return cls(state=_str(d, "state"), temp=_opt_float(d, "temp"), n_fresh=_int(d, "n_fresh"))


@dataclass(frozen=True)
class RemoteTemp:
    """An active external room-temperature feed."""

    temp: float | None
    source: str
    by: str
    age_s: int | None
    expires_in_s: int | None

    @classmethod
    def from_dict(cls, d: JSON) -> RemoteTemp:
        return cls(
            temp=_opt_float(d, "temp"),
            source=_str(d, "source"),
            by=_str(d, "by"),
            age_s=_opt_int(d, "age_s"),
            expires_in_s=_opt_int(d, "expires_in_s"),
        )


@dataclass(frozen=True)
class Settings:
    """Climate state of one head (``GET /api/settings``)."""

    power: str
    mode: str
    temperature: float | None
    fan: str
    vane: str
    wide_vane: str
    wide_vane_supported: bool
    connected: bool
    temp_unit: str
    room_temperature: float | None
    operating: bool
    compressor_frequency: int | None
    sub_mode: str | None
    stage: str | None
    error_code: str | None
    fault: bool
    park: ParkStatus | None
    room_sensor: RoomSensorSummary | None
    remote_temp: RemoteTemp | None
    raw: JSON = _raw()

    @classmethod
    def from_dict(cls, d: JSON) -> Settings:
        caps = _map(_map(d.get("caps")).get("wideVane"))
        park = d.get("park")
        rs = d.get("roomSensor")
        rt = d.get("remoteTemp")
        error_code = _opt_str(d, "errorCode")
        fault = _opt_bool(d, "fault")
        if fault is None:
            fault = bool(error_code) and error_code != "No Error"
        return cls(
            power=_str(d, "power", Power.OFF),
            mode=_str(d, "mode"),
            temperature=_opt_float(d, "temperature"),
            fan=_str(d, "fan"),
            vane=_str(d, "vane"),
            wide_vane=_str(d, "wideVane"),
            wide_vane_supported=_bool(caps, "show"),
            connected=_bool(d, "connected"),
            temp_unit=_str(d, "temp_unit", "C"),
            room_temperature=_opt_float(d, "roomTemperature"),
            operating=_bool(d, "operating"),
            compressor_frequency=_opt_int(d, "compressorFrequency"),
            sub_mode=_opt_str(d, "subMode"),
            stage=_opt_str(d, "stage"),
            error_code=error_code,
            fault=fault,
            park=ParkStatus.from_dict(park) if isinstance(park, Mapping) else None,
            room_sensor=RoomSensorSummary.from_dict(rs) if isinstance(rs, Mapping) else None,
            remote_temp=RemoteTemp.from_dict(rt) if isinstance(rt, Mapping) else None,
            raw=d,
        )

    @property
    def is_on(self) -> bool:
        return self.power.upper() == Power.ON


# ── /api/status ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PowerSupply:
    present: bool
    source: str
    input_mv: int | None
    vin_mv: int | None
    vbat_mv: int | None
    charging: bool
    battery_present: bool

    @classmethod
    def from_dict(cls, d: JSON) -> PowerSupply:
        return cls(
            present=_bool(d, "present"),
            source=_str(d, "source"),
            input_mv=_opt_int(d, "input_mv"),
            vin_mv=_opt_int(d, "vin_mv"),
            vbat_mv=_opt_int(d, "vbat_mv"),
            charging=_bool(d, "charging"),
            battery_present=_bool(d, "battery_present"),
        )


@dataclass(frozen=True)
class Diagnostics:
    boot_count: int
    brownout_count: int
    reset_reason: str
    last_was_brownout: bool
    vin_min_mv: int | None
    vin_min_ever_mv: int | None
    vin_sag_count: int
    wifi_drop_count: int
    wifi_drops_24h: int

    @classmethod
    def from_dict(cls, d: JSON) -> Diagnostics:
        return cls(
            boot_count=_int(d, "boot_count"),
            brownout_count=_int(d, "brownout_count"),
            reset_reason=_str(d, "reset_reason"),
            last_was_brownout=_bool(d, "last_was_brownout"),
            vin_min_mv=_opt_int(d, "vin_min_mv"),
            vin_min_ever_mv=_opt_int(d, "vin_min_ever_mv"),
            vin_sag_count=_int(d, "vin_sag_count"),
            wifi_drop_count=_int(d, "wifi_drop_count"),
            wifi_drops_24h=_int(d, "wifi_drops_24h"),
        )


@dataclass(frozen=True)
class Status:
    """Device health (``GET /api/status``)."""

    version: str
    hostname: str
    name: str
    ip: str
    ssid: str
    rssi: int | None
    unit_connected: bool
    mqtt_connected: bool
    mqtt_configured: bool
    uptime_s: int
    free_heap: int | None
    power: PowerSupply | None
    diag: Diagnostics | None
    raw: JSON = _raw()

    @classmethod
    def from_dict(cls, d: JSON) -> Status:
        power = d.get("power")
        diag = d.get("diag")
        return cls(
            version=_str(d, "version"),
            hostname=_str(d, "hostname"),
            name=_str(d, "name"),
            ip=_str(d, "ip"),
            ssid=_str(d, "ssid"),
            rssi=_opt_int(d, "rssi"),
            unit_connected=_bool(d, "unit_connected"),
            mqtt_connected=_bool(d, "mqtt_connected"),
            mqtt_configured=_bool(d, "mqtt_configured"),
            uptime_s=_int(d, "uptime_s"),
            free_heap=_opt_int(d, "free_heap"),
            power=PowerSupply.from_dict(power) if isinstance(power, Mapping) else None,
            diag=Diagnostics.from_dict(diag) if isinstance(diag, Mapping) else None,
            raw=d,
        )


# ── /api/capabilities ──────────────────────────────────────────────────


@dataclass(frozen=True)
class Capabilities:
    wide_vane_detected: str
    wide_vane_override: str
    wide_vane_detecting: bool
    wide_vane_supported: bool
    unit_connected: bool
    unit_on: bool
    raw: JSON = _raw()

    @classmethod
    def from_dict(cls, d: JSON) -> Capabilities:
        wv = _map(d.get("wideVane"))
        return cls(
            wide_vane_detected=_str(wv, "detected"),
            wide_vane_override=_str(wv, "override"),
            wide_vane_detecting=_bool(wv, "detecting"),
            wide_vane_supported=_bool(wv, "show"),
            unit_connected=_bool(d, "unit_connected"),
            unit_on=_bool(d, "unit_on"),
            raw=d,
        )


# ── /api/park ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParkConfig:
    """Off-at-setpoint config. ``shared_fields`` are group-wide while ``shared``."""

    enabled: bool
    delta_c: float | None
    min_off_s: int | None
    probe_enabled: bool
    probe_interval_s: int | None
    probe_duration_s: int | None
    shared: bool
    shared_fields: frozenset[str]
    status: ParkStatus | None
    raw: JSON = _raw()

    @classmethod
    def from_dict(cls, d: JSON) -> ParkConfig:
        status = d.get("status")
        return cls(
            enabled=_bool(d, "enabled"),
            delta_c=_opt_float(d, "delta_c"),
            min_off_s=_opt_int(d, "min_off_s"),
            probe_enabled=_bool(d, "probe_enabled"),
            probe_interval_s=_opt_int(d, "probe_interval_s"),
            probe_duration_s=_opt_int(d, "probe_duration_s"),
            shared=_bool(d, "shared"),
            shared_fields=frozenset(f for f in _list(d, "shared_fields") if isinstance(f, str)),
            status=ParkStatus.from_dict(status) if isinstance(status, Mapping) else None,
            raw=d,
        )


# ── /api/group ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GroupMember:
    uid: str
    name: str
    state: str
    configured_demand: str
    mode: str
    room_temp: float | None
    target_temp: float | None
    room_sensor_state: str
    ip: str
    operating: bool | None
    standby: bool | None

    @classmethod
    def from_dict(cls, d: JSON) -> GroupMember:
        return cls(
            uid=_str(d, "uid"),
            name=_str(d, "name"),
            state=_str(d, "state"),
            configured_demand=_str(d, "configured_demand"),
            mode=_str(d, "mode"),
            room_temp=_opt_float(d, "roomTemp"),
            target_temp=_opt_float(d, "targetTemp"),
            room_sensor_state=_str(d, "rs"),
            ip=_str(d, "ip"),
            operating=_opt_bool(d, "operating"),
            standby=_opt_bool(d, "standby"),
        )


@dataclass(frozen=True)
class TandemMember:
    uid: str
    fresh: bool
    capable: bool
    wants: str
    need: str
    directive: str

    @classmethod
    def from_dict(cls, d: JSON) -> TandemMember:
        return cls(
            uid=_str(d, "uid"),
            fresh=_bool(d, "fresh"),
            capable=_bool(d, "capable"),
            wants=_str(d, "wants"),
            need=_str(d, "need"),
            directive=_str(d, "directive"),
        )


@dataclass(frozen=True)
class Tandem:
    """Heat/cool time-slicing across one outdoor unit's heads."""

    enabled: bool
    min_slice_s: int | None
    max_slice_s: int | None
    settle_s: int | None
    available: bool
    active: bool
    mode: str
    phase: str
    elapsed_s: int | None
    decide_s: int | None
    coordinator: str
    is_coordinator: bool
    members: tuple[TandemMember, ...]

    @classmethod
    def from_dict(cls, d: JSON) -> Tandem:
        return cls(
            enabled=_bool(d, "enabled"),
            min_slice_s=_opt_int(d, "min_slice_s"),
            max_slice_s=_opt_int(d, "max_slice_s"),
            settle_s=_opt_int(d, "settle_s"),
            available=_bool(d, "available"),
            active=_bool(d, "active"),
            mode=_str(d, "mode"),
            phase=_str(d, "phase"),
            elapsed_s=_opt_int(d, "elapsed_s"),
            decide_s=_opt_int(d, "decide_s"),
            coordinator=_str(d, "coordinator"),
            is_coordinator=_bool(d, "is_coordinator"),
            members=tuple(
                TandemMember.from_dict(m) for m in _list(d, "members") if isinstance(m, Mapping)
            ),
        )

    def member(self, uid: str) -> TandemMember | None:
        return next((m for m in self.members if m.uid == uid), None)


@dataclass(frozen=True)
class Group:
    """Membership of the outdoor-unit group (``GET /api/group``)."""

    in_group: bool
    group_id: str
    label: str
    protocol_version: int
    self_member: GroupMember | None
    #: The other heads on this outdoor unit (``self_member`` excluded).
    members: tuple[GroupMember, ...]
    member_count: int
    status: str
    locked_mode: str | None
    locked_by: str
    conflicts: tuple[Any, ...]
    warnings: tuple[Any, ...]
    tandem: Tandem | None
    raw: JSON = _raw()

    @classmethod
    def from_dict(cls, d: JSON) -> Group:
        me = d.get("self")
        sl = d.get("slice")
        return cls(
            in_group=_bool(d, "in_group"),
            group_id=_str(d, "group_id"),
            label=_str(d, "group_label"),
            protocol_version=_int(d, "protocol_version"),
            self_member=GroupMember.from_dict(me) if isinstance(me, Mapping) else None,
            members=tuple(
                GroupMember.from_dict(m) for m in _list(d, "members") if isinstance(m, Mapping)
            ),
            member_count=_int(d, "member_count"),
            status=_str(d, "status"),
            locked_mode=_opt_str(d, "locked_mode"),
            locked_by=_str(d, "locked_by"),
            conflicts=tuple(_list(d, "conflicts")),
            warnings=tuple(_list(d, "warnings")),
            tandem=Tandem.from_dict(sl) if isinstance(sl, Mapping) else None,
            raw=d,
        )


# ── /api/sensors ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class RoomSensor:
    id: str
    kind: str
    name: str
    fresh: bool
    temp: float | None
    humidity: float | None
    battery: int | None
    rssi: int | None
    temp_age_s: int | None
    seen_age_s: int | None
    stale_after_s: int | None

    @classmethod
    def from_dict(cls, d: JSON) -> RoomSensor:
        return cls(
            id=_str(d, "id"),
            kind=_str(d, "kind"),
            name=_str(d, "name"),
            fresh=_bool(d, "fresh"),
            temp=_opt_float(d, "temp"),
            humidity=_opt_float(d, "humidity"),
            battery=_opt_int(d, "battery"),
            rssi=_opt_int(d, "rssi"),
            temp_age_s=_opt_int(d, "temp_age_s"),
            seen_age_s=_opt_int(d, "seen_age_s"),
            stale_after_s=_opt_int(d, "stale_after_s"),
        )


@dataclass(frozen=True)
class Sensors:
    active: bool
    temp: float | None
    n_fresh: int
    max: int
    sensors: tuple[RoomSensor, ...]
    raw: JSON = _raw()

    @classmethod
    def from_dict(cls, d: JSON) -> Sensors:
        return cls(
            active=_bool(d, "active"),
            temp=_opt_float(d, "temp"),
            n_fresh=_int(d, "n_fresh"),
            max=_int(d, "max"),
            sensors=tuple(
                RoomSensor.from_dict(s) for s in _list(d, "sensors") if isinstance(s, Mapping)
            ),
            raw=d,
        )


# ── /api/events ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Event:
    seq: int
    ts: int
    uptime_s: int
    category: int
    actor: int
    message: str
    name: str
    ip: str

    @classmethod
    def from_dict(cls, d: JSON) -> Event:
        return cls(
            seq=_int(d, "seq"),
            ts=_int(d, "ts"),
            uptime_s=_int(d, "up"),
            category=_int(d, "cat"),
            actor=_int(d, "act"),
            message=_str(d, "msg"),
            name=_str(d, "name"),
            ip=_str(d, "ip"),
        )

    @property
    def category_enum(self) -> EventCategory | None:
        try:
            return EventCategory(self.category)
        except ValueError:
            return None

    @property
    def actor_enum(self) -> EventActor | None:
        try:
            return EventActor(self.actor)
        except ValueError:
            return None


@dataclass(frozen=True)
class EventLog:
    events: tuple[Event, ...]
    now_epoch: int
    clock_valid: bool
    seq: int

    @classmethod
    def from_dict(cls, d: JSON) -> EventLog:
        return cls(
            events=tuple(Event.from_dict(e) for e in _list(d, "events") if isinstance(e, Mapping)),
            now_epoch=_int(d, "now_epoch"),
            clock_valid=_bool(d, "clock_valid"),
            seq=_int(d, "seq"),
        )


# ── /api/update, /api/ota/status ───────────────────────────────────────


@dataclass(frozen=True)
class UpdateInfo:
    current: str
    latest: str
    update_available: bool
    checking: bool
    checked: bool
    published_at: str
    release_url: str
    error: str
    last_check_age_s: int | None
    raw: JSON = _raw()

    @classmethod
    def from_dict(cls, d: JSON) -> UpdateInfo:
        return cls(
            current=_str(d, "current"),
            latest=_str(d, "latest"),
            update_available=_bool(d, "update_available"),
            checking=_bool(d, "checking"),
            checked=_bool(d, "checked"),
            published_at=_str(d, "published_at"),
            release_url=_str(d, "release_url"),
            error=_str(d, "error"),
            last_check_age_s=_opt_int(d, "last_check_age_s"),
            raw=d,
        )


@dataclass(frozen=True)
class OtaStatus:
    state: str
    progress: int
    message: str
    busy: bool

    @classmethod
    def from_dict(cls, d: JSON) -> OtaStatus:
        return cls(
            state=_str(d, "state"),
            progress=_int(d, "progress"),
            message=_str(d, "message"),
            busy=_bool(d, "busy"),
        )


# ── /api/house/summary ─────────────────────────────────────────────────


@dataclass(frozen=True)
class HouseSummary:
    """Compact public summary of one head (no auth needed)."""

    uid: str
    name: str
    pv: int
    version: str
    ghash: str
    group_label: str
    unit_connected: bool
    power: str
    mode: str
    operating: bool
    room_temp: float | None
    room_sensor_state: str
    target_temp: float | None
    compressor_frequency: int | None
    raw: JSON = _raw()

    @classmethod
    def from_dict(cls, d: JSON) -> HouseSummary:
        return cls(
            uid=_str(d, "uid"),
            name=_str(d, "name"),
            pv=_int(d, "pv"),
            version=_str(d, "version"),
            ghash=_str(d, "ghash"),
            group_label=_str(d, "glabel"),
            unit_connected=_bool(d, "unit_connected"),
            power=_str(d, "power"),
            mode=_str(d, "mode"),
            operating=_bool(d, "operating"),
            room_temp=_opt_float(d, "roomTemp"),
            room_sensor_state=_str(d, "rs"),
            target_temp=_opt_float(d, "targetTemp"),
            compressor_frequency=_opt_int(d, "freq"),
            raw=d,
        )


# ── write results ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class RemoteTempLease:
    active: bool
    temp: float | None
    expires_in_s: int | None

    @classmethod
    def from_dict(cls, d: JSON) -> RemoteTempLease:
        return cls(
            active=_bool(d, "active"),
            temp=_opt_float(d, "temp"),
            expires_in_s=_opt_int(d, "expires_in_s"),
        )


@dataclass(frozen=True)
class Ticket:
    """A one-time ticket that lets a peer head mint a token for you."""

    ticket: str
    label: str
    scope: str
    expires: int | None

    @classmethod
    def from_dict(cls, d: JSON) -> Ticket:
        return cls(
            ticket=_str(d, "ticket"),
            label=_str(d, "label"),
            scope=_str(d, "scope"),
            expires=_opt_int(d, "expires"),
        )


@dataclass(frozen=True)
class TokenGrant:
    """A freshly minted integration token. ``token`` is only ever shown once."""

    token: str
    id: str
    label: str
    scope: str

    @classmethod
    def from_dict(cls, d: JSON) -> TokenGrant:
        return cls(
            token=_str(d, "token"),
            id=_str(d, "id"),
            label=_str(d, "label"),
            scope=_str(d, "scope"),
        )
