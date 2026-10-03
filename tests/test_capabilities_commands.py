import json
import uuid

import pytest

from samsung_local.capabilities import (PREFIX, device_type, directory_links,
                                        normalize, power_command, readable)
from samsung_local.mqtt import validate_command


def test_legacy_and_modern_directory():
    directory = [{"links": [{"href": "/power/0", "p": {"sec": True, "port": 49161}},
                            {"href": "/oic/sec/cred", "eps": [{"ep": "coaps://192.0.2.5:49162"}]}]}]
    assert directory_links(directory) == ["/power/0"]
    assert directory_links({"links": [{"href": "coaps://evil/x"}, {"href": "/temperature/0"}]}) == ["/temperature/0"]


@pytest.mark.parametrize("href", ["/oic/sec/cred", "/oic/sec/doxm", "/oic/sec/pstat", "/acl/0",
                                  "/power/../../oic/sec/cred", "https://example.org", "/file/0"])
def test_security_and_unknown_reads_disallowed(href):
    assert not readable(href)


def test_mappings_units_and_vendor_fallback():
    state, sensors = normalize({"/power/0": {"value": True}, "/power/vs/0": {PREFIX + "power": "Off"},
        "/temperature/0": {"temperature": 5, "units": "C"},
        "/energy/consumption/vs/0": {PREFIX + "instantaneousPower": -1, PREFIX + "cumulativePower": "1234"},
        "/operational/state/vs/0": {PREFIX + "state": "Run", PREFIX + "remainingTime": "01:20:00"}})
    assert state["power"] == 1
    assert state["temperature_0_temperature"] == 5
    assert sensors["temperature_0_temperature"]["unit"] == "C"
    assert not any(k.endswith("power_w") for k in state)
    assert state["energy_consumption_vs_0_energy_wh"] == 1234
    assert state["operational_state_vs_0_remainingTime"] == "01:20:00"


def test_no_invented_temperature_unit():
    state, sensors = normalize({"/temperature/0": {"temperature": 7}})
    assert sensors["temperature_0_temperature"]["unit"] is None


def test_type_detection_does_not_confuse_washer_board_with_dryer():
    assert device_type([], {PREFIX + "modelNum": "DA_WM_22K", PREFIX + "description": "Samsung_DV90ABC"}) == "dryer"
    assert device_type(["oic.d.refrigerator"], {}) == "refrigerator"


def test_power_writes_only_reviewed_mapping():
    assert power_command("airconditioner", {"/power/0": {"value": False}}, "on") == ("/power/0", {"value": True})
    assert power_command("air_purifier", {"/power/vs/0": {PREFIX + "power": "On"}}, "off")[1] == {PREFIX + "power": "Off"}
    for kind in ("washer", "oven", "unknown", "refrigerator"):
        with pytest.raises(ValueError):
            power_command(kind, {"/power/0": {"value": True}}, "on")


def test_appliance_remote_control_disable_is_respected():
    with pytest.raises(ValueError):
        power_command("airconditioner", {"/power/0": {"value": True},
                                        "/remotectrl/0": {"value": False}}, "on")


def command(**changes):
    return json.dumps(dict({"id": str(uuid.uuid4()), "timestamp": 1000, "value": "on"}, **changes)).encode()


@pytest.mark.parametrize("payload,retained", [
    (b"on", False), (command(), True), (command(timestamp=900), False),
    (command(timestamp=1010), False), (command(id="bad"), False),
    (command(value="start"), False), (command(timestamp=float("nan")), False), (b"a" * 1025, False),
    (command(id=42), False), (command(id=None), False),
])
def test_stale_retained_or_malformed_commands_rejected(payload, retained):
    with pytest.raises((ValueError, TypeError)):
        validate_command(payload, retained, 1000)


def test_recent_command_accepted():
    assert validate_command(command(), False, 1000)["value"] == "on"
