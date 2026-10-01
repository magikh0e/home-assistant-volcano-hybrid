"""Tests for the Venty/Veazy state decoded from frames."""

from __future__ import annotations

from typing import Any

from custom_components.volcano_hybrid.volcano_ble import qvap_frames as f
from custom_components.volcano_hybrid.volcano_ble.const import (
    DeviceFamily,
    VolcanoSensor,
)
from custom_components.volcano_hybrid.volcano_ble.qvap_data import (
    VeazyData,
    VentyData,
)

from . import FakeDevice


def _status(**overrides: int | bool | None) -> f.QvapStatus:
    values: dict[str, Any] = {
        "current_temp": 184,
        "target_temp": 186,
        "boost": 10,
        "superboost": 20,
        "battery": 85,
        "countdown": 120,
        "heater_mode": 2,
        "charging": True,
        "settings": f.BIT_SETPOINT_REACHED | f.BIT_CHARGE_OPTIMIZATION,
        "settings2": f.BIT2_PERMANENT_BLUETOOTH,
    }
    values.update(overrides)
    return f.QvapStatus(**values)


def test_apply_status_on_a_venty() -> None:
    """Every status field lands in the data, and settings2 only when present."""
    data: VentyData = FakeDevice(DeviceFamily.VENTY).data
    data.apply_status(_status())
    assert data.current_temp == 184
    assert data.set_temp == 186
    assert data.boost_temp == 10
    assert data.superboost_temp == 20
    assert data.battery == 85
    assert data.auto_off_countdown == 120
    assert data.heater is True
    assert data.heater_mode == 2
    assert data.heater_mode_name == "boost"
    assert data.boost_mode is True
    assert data.superboost_mode is False
    assert data.charging is True
    assert data.at_temperature is True
    assert data.showing_celsius is True
    assert data.charge_optimization is True
    assert data.charge_limit is False
    assert data.boost_visualization is False
    assert data.target_changed_on_device is False
    assert data.permanent_bluetooth is True
    assert data.permanent_bluetooth_enabled is True

    data.apply_status(_status(heater_mode=0, settings=f.BIT_FAHRENHEIT, settings2=None))
    assert data.heater is False
    assert data.heater_mode_name == "off"
    assert data.showing_celsius is False
    assert data.permanent_bluetooth is True  # unchanged when the frame omits it


def test_mode_properties_are_unknown_before_a_status() -> None:
    """Nothing is claimed about the heater mode until a status arrives."""
    data: VentyData = FakeDevice(DeviceFamily.VENTY).data
    assert data.boost_mode is None
    assert data.superboost_mode is None
    assert data.heater_mode_name is None
    data.apply_status(_status(heater_mode=3))
    assert data.superboost_mode is True
    assert data.heater_mode_name == "superboost"
    data.apply_status(_status(heater_mode=7))
    assert data.heater_mode_name is None


def test_veazy_inverts_the_visualization_bit() -> None:
    """The Veazy stores the visualisation bit inverted (spec §2.3)."""
    data: VeazyData = FakeDevice(DeviceFamily.VEAZY).data
    data.apply_status(_status(settings=f.BIT_BOOST_VISUALIZATION))
    assert data.boost_visualization is False
    data.apply_status(_status(settings=0))
    assert data.boost_visualization is True


def test_apply_firmware_and_bootloader_mode() -> None:
    """A cleared application bit means the device sits in its bootloader."""
    data: VentyData = FakeDevice(DeviceFamily.VENTY).data
    data.apply_firmware(f.QvapFirmware(True, False, False, "V01.09", "V00.05"))
    assert data.firmware_version == "V01.09"
    assert data.bootloader_version == "V00.05"
    assert data.bootloader_mode is False
    data.apply_firmware(f.QvapFirmware(False, True, False, "V01.09", "V00.05"))
    assert data.bootloader_mode is True
    assert data.invalid_application is True


def test_apply_usage_identity_and_settings6() -> None:
    """Usage counters, serial, colour and the 0x06 settings are taken over."""
    data: VeazyData = FakeDevice(DeviceFamily.VEAZY).data
    data.apply_usage(f.QvapUsage(150, 40))
    assert data.heat_time == 150
    assert data.charging_time == 40
    data.apply_identity(f.QvapIdentity("VZ654321", 3))
    assert data.serial_number == "VZ654321"
    assert data.color == "pink"
    data.apply_identity(f.QvapIdentity("VZ654321", 9))
    assert data.color == "black"
    data.apply_identity(f.QvapIdentity("VZ654321", None))
    assert data.color == "black"  # unchanged when the frame omits it
    data.apply_settings6(f.QvapSettings(7, True, False))
    assert data.brightness == 7
    assert data.vibration is True
    assert data.boost_timeout_disabled is False


def test_capabilities_differ_between_venty_and_veazy() -> None:
    """Only the Veazy writes permanent Bluetooth and reports a colour."""
    venty = FakeDevice(DeviceFamily.VENTY).data
    veazy = FakeDevice(DeviceFamily.VEAZY).data
    assert VolcanoSensor.PERMANENT_BLUETOOTH_ENABLED in venty.capabilities
    assert VolcanoSensor.PERMANENT_BLUETOOTH not in venty.capabilities
    assert VolcanoSensor.PERMANENT_BLUETOOTH in veazy.capabilities
    assert VolcanoSensor.COLOR in veazy.capabilities
    assert VolcanoSensor.COLOR not in venty.capabilities
    assert venty.model_name == "Venty"
    assert veazy.model_name == "Veazy"
