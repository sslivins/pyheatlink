"""Constants shared by the HeatLink HTTP API."""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Final

DEFAULT_PORT: Final = 80
DEFAULT_TIMEOUT: Final = 10.0

ZEROCONF_TYPE: Final = "_mmhvac._tcp.local."

#: Highest /api/info ``api_version`` this library was written against.
SUPPORTED_API_VERSION: Final = 1

REMOTE_TEMP_TTL_MIN: Final = 60
REMOTE_TEMP_TTL_MAX: Final = 3600
REMOTE_TEMP_TTL_DEFAULT: Final = 600


class Scope(StrEnum):
    """Integration token scopes, weakest first."""

    READ = "read"
    CONTROL = "control"
    ADMIN = "admin"


class Feature(StrEnum):
    """Feature flags reported in /api/info ``features``."""

    TOKENS = "tokens"
    TOKEN_TICKETS = "token_tickets"
    EVENTS = "events"
    HISTORY = "history"
    PARK = "park"
    ROOM_SENSORS = "room_sensors"
    GROUP = "group"
    TANDEM = "tandem"
    REMOTE_TEMP = "remote_temp"
    FAULT = "fault"
    SHARED_FIELDS = "shared_fields"
    MQTT_DISCOVERY_SWITCH = "mqtt_discovery_switch"


class Power(StrEnum):
    ON = "ON"
    OFF = "OFF"


class Mode(StrEnum):
    HEAT = "HEAT"
    DRY = "DRY"
    COOL = "COOL"
    FAN = "FAN"
    AUTO = "AUTO"


FAN_SPEEDS: Final = ("AUTO", "QUIET", "1", "2", "3", "4")
VANE_POSITIONS: Final = ("AUTO", "1", "2", "3", "4", "5", "SWING")
WIDE_VANE_POSITIONS: Final = ("<<", "<", "|", ">", ">>", "<>", "SWING")


class EventCategory(IntEnum):
    MODE = 0
    POWER = 1
    SETPOINT = 2
    FAN = 3
    GROUP = 4
    MEMBERSHIP = 5
    OTA = 6
    NET = 7
    UNIT = 8
    FAULT = 9
    SYSTEM = 10


class EventActor(IntEnum):
    SYSTEM = 0
    WEB_UI = 1
    HOME_ASSISTANT = 2
    GROUP = 3
    LOCAL = 4


DIAG_COUNTERS: Final = ("brownout", "wifi-drops", "vin-min")
