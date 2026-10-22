from __future__ import annotations

import pytest

from pyheatlink import (
    Capabilities,
    EventLog,
    Feature,
    Group,
    HouseSummary,
    Info,
    OtaStatus,
    ParkConfig,
    Sensors,
    Settings,
    Status,
    UpdateInfo,
)
from pyheatlink.const import EventActor, EventCategory
from pyheatlink.models import Event, RemoteTemp

from .conftest import load

ALL_MODELS = [
    (Info, "info"),
    (Settings, "settings"),
    (Status, "status"),
    (Capabilities, "capabilities"),
    (ParkConfig, "park"),
    (Group, "group"),
    (Sensors, "sensors"),
    (EventLog, "events"),
    (UpdateInfo, "update"),
    (OtaStatus, "ota_status"),
    (HouseSummary, "house_summary"),
]


def test_info() -> None:
    info = Info.from_dict(load("info"))
    assert info.uid == "6dac"
    assert info.api_version == 1
    assert info.auth.open_climate and info.auth.tokens
    assert info.has(Feature.REMOTE_TEMP) and info.has("tandem")
    assert not info.has("something_new")
    assert info.mqtt is not None and info.mqtt.discovery
    assert info.group is not None and info.group.ghash == "bb66e0db"


def test_info_ungrouped_without_mqtt() -> None:
    info = Info.from_dict({"uid": "abcd", "group": {}, "features": ["park", 7]})
    assert info.group is None
    assert info.mqtt is None
    assert info.features == frozenset({"park"})


def test_settings() -> None:
    s = Settings.from_dict(load("settings"))
    assert not s.is_on
    assert s.mode == "COOL"
    assert s.temperature == 16
    assert s.room_temperature == 17.5
    assert s.connected
    assert not s.wide_vane_supported
    assert s.error_code == "No Error" and not s.fault
    assert s.park is not None and s.park.slicing and s.park.next_probe_s is None
    assert s.room_sensor is not None and s.room_sensor.temp == 17.4
    assert s.remote_temp is None


def test_settings_remote_temp_and_fault_fallback() -> None:
    s = Settings.from_dict(
        {
            "power": "ON",
            "errorCode": "E6",
            "remoteTemp": {"temp": 21.5, "source": "api", "by": "ha", "expires_in_s": None},
        }
    )
    assert s.is_on
    assert s.fault  # derived from errorCode when firmware has no `fault`
    assert s.remote_temp == RemoteTemp(21.5, "api", "ha", None, None)


def test_status() -> None:
    st = Status.from_dict(load("status"))
    assert st.version == "1.5.2"
    assert st.rssi == -67
    assert st.power is not None and st.power.source == "vin"
    assert st.diag is not None and st.diag.boot_count == 143


def test_group_and_tandem() -> None:
    g = Group.from_dict(load("group"))
    assert g.in_group and g.label == "Bedrooms"
    assert g.self_member is not None and g.self_member.uid == "6dac"
    assert [m.uid for m in g.members] == ["e6c8", "e6ec", "3e30"]
    assert g.members[1].room_sensor_state == ""
    assert g.tandem is not None
    assert g.tandem.coordinator == "3e30" and not g.tandem.is_coordinator
    member = g.tandem.member("3e30")
    assert member is not None and member.directive == "run"
    assert g.tandem.member("nope") is None


def test_park_shared_fields() -> None:
    p = ParkConfig.from_dict(load("park"))
    assert p.shared and "min_off_s" in p.shared_fields and "delta_c" not in p.shared_fields
    assert p.delta_c == 0.5


def test_sensors() -> None:
    s = Sensors.from_dict(load("sensors"))
    assert s.max == 4
    assert s.sensors[0].kind == "bthome" and s.sensors[0].humidity == 69


def test_events() -> None:
    log = EventLog.from_dict(load("events"))
    assert log.seq == 641 and log.clock_valid
    first = log.events[0]
    assert first.category_enum is EventCategory.SYSTEM
    assert first.actor_enum is EventActor.SYSTEM
    assert log.events[3].name == "admin"
    unknown = Event.from_dict({"cat": 99, "act": 42})
    assert unknown.category_enum is None and unknown.actor_enum is None


def test_house_summary() -> None:
    h = HouseSummary.from_dict(load("house_summary"))
    assert h.ghash == "bb66e0db" and h.compressor_frequency == 0


@pytest.mark.parametrize(("model", "name"), ALL_MODELS)
def test_models_tolerate_empty_payload(model: type, name: str) -> None:
    model.from_dict({})


@pytest.mark.parametrize(("model", "name"), ALL_MODELS)
def test_models_tolerate_wrong_types(model: type, name: str) -> None:
    junk = {k: [] if not isinstance(v, list) else "x" for k, v in load(name).items()}
    model.from_dict(junk)


def test_bool_is_not_a_number() -> None:
    s = Settings.from_dict({"temperature": True, "compressorFrequency": False})
    assert s.temperature is None and s.compressor_frequency is None


def test_raw_is_kept_but_not_compared() -> None:
    a = OtaStatus.from_dict({"state": "idle"})
    assert a == OtaStatus.from_dict({"state": "idle", "extra": 1})
    u = UpdateInfo.from_dict({"current": "1", "new_field": True})
    assert u.raw["new_field"] is True
