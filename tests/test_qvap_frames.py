"""Byte-exact tests for the Venty/Veazy frame codec (VENTY_BLE_SPEC.md §2-3)."""

from __future__ import annotations

import pytest

from custom_components.volcano_hybrid.volcano_ble import qvap_frames as f

# A status reply: 183.8 °C current, 186.0 °C target, boost 10, superboost 20,
# battery 85 %, 120 s countdown, boost mode, charger on, settings 0x0A
# (setpoint reached + charge optimisation), settings2 permanent BT.
STATUS = bytes(
    [
        0x01,
        0x00,
        0x2E,
        0x07,
        0x44,
        0x07,
        10,
        20,
        85,
        0x78,
        0x00,
        2,
        0,
        1,
        0x0A,
        0,
        0x01,
        0,
        0,
        0,
    ]
)


def test_parse_status() -> None:
    """Parse status."""
    status = f.parse_status(STATUS)
    assert status.current_temp == 184
    assert status.target_temp == 186
    assert status.boost == 10
    assert status.superboost == 20
    assert status.battery == 85
    assert status.countdown == 120
    assert status.heater_mode == 2
    assert status.charging is True
    assert status.settings == 0x0A
    assert status.settings2 == 0x01


def test_parse_status_without_settings2() -> None:
    """Older firmware answers 15 bytes; settings2 is then unknown."""
    status = f.parse_status(STATUS[:15])
    assert status.settings2 is None


def test_parse_status_rejects_other_frames() -> None:
    """Parse status rejects other frames."""
    with pytest.raises(ValueError, match="0x02"):
        f.parse_status(bytes([0x02]) + STATUS[1:])
    with pytest.raises(ValueError, match="short"):
        f.parse_status(STATUS[:14])


def test_build_request_is_a_zeroed_20_byte_frame() -> None:
    """Build request is a zeroed 20 byte frame."""
    frame = f.build_request(f.CMD_FIRMWARE)
    assert len(frame) == 20
    assert frame[0] == 0x02
    assert not any(frame[1:])


def test_build_target_write() -> None:
    """Build target write."""
    frame = f.build_target_write(185)
    assert frame[0] == 0x01
    assert frame[1] == f.MASK_SET_TEMP
    assert frame[4:6] == (1850).to_bytes(2, "little")
    assert not any(frame[6:])


def test_build_boost_and_superboost_writes() -> None:
    """Build boost and superboost writes."""
    assert f.build_boost_write(12)[1:7] == bytes([f.MASK_BOOST, 0, 0, 0, 0, 12])
    assert f.build_superboost_write(15)[1:8] == bytes(
        [f.MASK_SUPERBOOST, 0, 0, 0, 0, 0, 15]
    )


def test_build_heater_write_only_toggles_between_off_and_normal() -> None:
    """Modes 2/3 are never written: entering boost over BLE is speculative."""
    on = f.build_heater_write(True)
    off = f.build_heater_write(False)
    assert on[1] == off[1] == f.MASK_HEATER
    assert on[11] == 1
    assert off[11] == 0


def test_build_settings_write_is_masked() -> None:
    """Build settings write is masked."""
    frame = f.build_settings_write(f.BIT_CHARGE_LIMIT, f.BIT_CHARGE_LIMIT)
    assert frame[1] == f.MASK_SETTINGS
    assert frame[14] == 0x20
    assert frame[15] == 0x20
    clear = f.build_settings_write(0, f.BIT_CHARGE_LIMIT, 0, f.BIT2_PERMANENT_BLUETOOTH)
    assert clear[14:18] == bytes([0x00, 0x20, 0x00, 0x01])


def test_build_settings6_write_is_seven_bytes() -> None:
    """Build settings6 write is seven bytes."""
    frame = f.build_settings6_write(f.CMD6_BRIGHTNESS, brightness=9)
    assert frame == bytes([0x06, 0x01, 9, 0, 0, 0, 0])
    frame = f.build_settings6_write(f.CMD6_VIBRATION, vibration=True)
    assert frame == bytes([0x06, 0x08, 0, 0, 0, 1, 0])
    frame = f.build_settings6_write(f.CMD6_BOOST_TIMEOUT, timeout_disabled=True)
    assert frame == bytes([0x06, 0x10, 0, 0, 0, 0, 1])


def test_build_find_device() -> None:
    """Build find device."""
    assert f.build_find_device()[:2] == bytes([0x0D, 0x01])


def test_parse_firmware_decodes_the_strings() -> None:
    """Versions are UTF-8 at offsets 2 and 11, not raw bytes (spec §3.1)."""
    frame = bytes([0x02, 0x01]) + b"V01.09" + bytes(3) + b"V00.05" + bytes(3)
    firmware = f.parse_firmware(frame)
    assert firmware.application_running is True
    assert firmware.invalid_application is False
    assert firmware.invalid_bootloader is False
    assert firmware.firmware_version == "V01.09"
    assert firmware.bootloader_version == "V00.05"

    in_bootloader = f.parse_firmware(bytes([0x02, 0x30]) + frame[2:])
    assert in_bootloader.application_running is False
    assert in_bootloader.invalid_application is True
    assert in_bootloader.invalid_bootloader is True


def test_parse_usage() -> None:
    """Parse usage."""
    frame = (
        bytes([0x04]) + (100000).to_bytes(3, "little") + (5000).to_bytes(3, "little")
    )
    frame += bytes(20 - len(frame))
    usage = f.parse_usage(frame)
    assert usage.heater_minutes == 100000
    assert usage.charging_minutes == 5000


def test_parse_identity() -> None:
    """Parse identity."""
    frame = bytearray(20)
    frame[0] = 0x05
    frame[9:15] = b"123456"
    frame[15:17] = b"VZ"
    frame[18] = 3
    identity = f.parse_identity(bytes(frame))
    assert identity.serial == "VZ123456"
    assert identity.color_index == 3
    assert f.parse_identity(bytes(frame[:18])).color_index is None


def test_parse_settings6() -> None:
    """Parse settings6."""
    settings = f.parse_settings6(bytes([0x06, 0, 7, 0, 0, 1, 0]))
    assert settings.brightness == 7
    assert settings.vibration is True
    assert settings.boost_timeout_disabled is False


def test_parse_advertising() -> None:
    """Parse advertising."""
    assert f.parse_advertising(bytes([0x1D, 0x10])) is True
    assert f.parse_advertising(bytes([0x1D, 0x00])) is False


def test_forbidden_commands_are_the_bootloader_ones() -> None:
    """Forbidden commands are the bootloader ones."""
    assert {0x0C, 0x30} == f.FORBIDDEN_COMMANDS
