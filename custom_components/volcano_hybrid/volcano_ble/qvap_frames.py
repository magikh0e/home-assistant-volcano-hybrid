"""
Frames of the Venty/Veazy ("Qvap") protocol, built and parsed byte for byte.

Every table here mirrors one in VENTY_BLE_SPEC.md; nothing in this module
touches Bluetooth, so it can be tested against the spec's own examples.
"""

from __future__ import annotations

from dataclasses import dataclass

FRAME_LENGTH = 20
SETTINGS6_LENGTH = 7

# Command ids (spec §2, §3)
CMD_STATUS = 0x01
CMD_FIRMWARE = 0x02
CMD_USAGE = 0x04
CMD_IDENTITY = 0x05
CMD_SETTINGS = 0x06
CMD_BOOTLOADER_SWITCH = 0x0C
CMD_FIND_DEVICE = 0x0D
CMD_ADVERTISING = 0x1D
CMD_BOOTLOADER = 0x30
# Spec §3.8: these put the device into, or drive, its bootloader.
FORBIDDEN_COMMANDS = frozenset({CMD_BOOTLOADER_SWITCH, CMD_BOOTLOADER})

# Status write masks, byte 1 (spec §2.2)
MASK_SET_TEMP = 0x02
MASK_BOOST = 0x04
MASK_SUPERBOOST = 0x08
MASK_HEATER = 0x20
MASK_SETTINGS = 0x80

# Settings bits, byte 14 (spec §2.3)
BIT_FAHRENHEIT = 0x01
BIT_SETPOINT_REACHED = 0x02
BIT_CHARGE_OPTIMIZATION = 0x08
BIT_TARGET_CHANGED = 0x10
BIT_CHARGE_LIMIT = 0x20
BIT_BOOST_VISUALIZATION = 0x40
# Settings2 bits, byte 16
BIT2_PERMANENT_BLUETOOTH = 0x01

# Command 0x06 masks (spec §3.4)
CMD6_BRIGHTNESS = 0x01
CMD6_VIBRATION = 0x08
CMD6_BOOST_TIMEOUT = 0x10

# Firmware flags, command 0x02 byte 1 (spec §3.1)
APP_RUNNING = 0x01
APP_INVALID = 0x10
BOOTLOADER_INVALID = 0x20

HEATER_MODE_OFF = 0
HEATER_MODE_ON = 1
HEATER_MODE_BOOST = 2
HEATER_MODE_SUPERBOOST = 3

_STATUS_MIN = 15
_STATUS_WITH_SETTINGS2 = 17
_FIRMWARE_MIN = 19
_USAGE_MIN = 7
_IDENTITY_MIN = 18
_IDENTITY_WITH_COLOR = 19
_ADVERTISING_MIN = 2


@dataclass(frozen=True)
class QvapStatus:
    """One command-0x01 reply (spec §2.1)."""

    current_temp: int
    target_temp: int
    boost: int
    superboost: int
    battery: int
    countdown: int
    heater_mode: int
    charging: bool
    settings: int
    settings2: int | None


@dataclass(frozen=True)
class QvapFirmware:
    """One command-0x02 reply (spec §3.1)."""

    application_running: bool
    invalid_application: bool
    invalid_bootloader: bool
    firmware_version: str
    bootloader_version: str


@dataclass(frozen=True)
class QvapUsage:
    """One command-0x04 reply (spec §3.2)."""

    heater_minutes: int
    charging_minutes: int


@dataclass(frozen=True)
class QvapIdentity:
    """One command-0x05 reply (spec §3.3)."""

    serial: str
    color_index: int | None


@dataclass(frozen=True)
class QvapSettings:
    """One command-0x06 reply (spec §3.4)."""

    brightness: int
    vibration: bool
    boost_timeout_disabled: bool


def _check(frame: bytes, cmd: int, minimum: int) -> None:
    if not frame or frame[0] != cmd:
        msg = (
            f"expected command 0x{cmd:02x}, got 0x{frame[0]:02x}" if frame else "empty"
        )
        raise ValueError(msg)
    if len(frame) < minimum:
        msg = f"frame too short for command 0x{cmd:02x}: {len(frame)} < {minimum}"
        raise ValueError(msg)


def _u16(frame: bytes, offset: int) -> int:
    return int.from_bytes(frame[offset : offset + 2], "little")


# -- builders ----------------------------------------------------------------


def _frame(cmd: int, mask: int = 0, fields: dict[int, int] | None = None) -> bytes:
    frame = bytearray(FRAME_LENGTH)
    frame[0] = cmd
    frame[1] = mask
    for offset, value in (fields or {}).items():
        frame[offset] = value & 0xFF
    return bytes(frame)


def build_request(cmd: int) -> bytes:
    """Build a read request: the command id and nothing else."""
    return _frame(cmd)


def build_target_write(celsius: int) -> bytes:
    """Set the target temperature (x10, bytes 4-5)."""
    raw = celsius * 10
    return _frame(CMD_STATUS, MASK_SET_TEMP, {4: raw, 5: raw >> 8})


def build_boost_write(offset: int) -> bytes:
    """Set the boost offset (byte 6)."""
    return _frame(CMD_STATUS, MASK_BOOST, {6: offset})


def build_superboost_write(offset: int) -> bytes:
    """Set the superboost offset (byte 7)."""
    return _frame(CMD_STATUS, MASK_SUPERBOOST, {7: offset})


def build_heater_write(on: bool) -> bytes:
    """Switch the heater between off and normal heating (byte 11)."""
    return _frame(
        CMD_STATUS, MASK_HEATER, {11: HEATER_MODE_ON if on else HEATER_MODE_OFF}
    )


def build_settings_write(bits: int, mask: int, bits2: int = 0, mask2: int = 0) -> bytes:
    """Change settings bits: values in bytes 14/16, which bits in 15/17."""
    return _frame(CMD_STATUS, MASK_SETTINGS, {14: bits, 15: mask, 16: bits2, 17: mask2})


def build_settings6_write(
    mask: int,
    *,
    brightness: int = 0,
    vibration: bool = False,
    timeout_disabled: bool = False,
) -> bytes:
    """Build the 7-byte command 0x06 write."""
    return bytes(
        [
            CMD_SETTINGS,
            mask,
            brightness & 0xFF,
            0,
            0,
            int(vibration),
            int(timeout_disabled),
        ]
    )


def build_find_device() -> bytes:
    """Make the device signal its position."""
    return _frame(CMD_FIND_DEVICE, 0x01)


# -- parsers -----------------------------------------------------------------


def parse_status(frame: bytes) -> QvapStatus:
    """Decode a command-0x01 reply."""
    _check(frame, CMD_STATUS, _STATUS_MIN)
    return QvapStatus(
        current_temp=round(_u16(frame, 2) / 10),
        target_temp=round(_u16(frame, 4) / 10),
        boost=frame[6],
        superboost=frame[7],
        battery=frame[8],
        countdown=_u16(frame, 9),
        heater_mode=frame[11],
        charging=frame[13] > 0,
        settings=frame[14],
        settings2=frame[16] if len(frame) >= _STATUS_WITH_SETTINGS2 else None,
    )


def parse_firmware(frame: bytes) -> QvapFirmware:
    """Decode a command-0x02 reply; the versions are UTF-8 strings."""
    _check(frame, CMD_FIRMWARE, _FIRMWARE_MIN)
    flags = frame[1]
    return QvapFirmware(
        application_running=bool(flags & APP_RUNNING),
        invalid_application=bool(flags & APP_INVALID),
        invalid_bootloader=bool(flags & BOOTLOADER_INVALID),
        firmware_version=frame[2:8].decode("utf-8", "replace").strip("\x00 "),
        bootloader_version=frame[11:17].decode("utf-8", "replace").strip("\x00 "),
    )


def parse_usage(frame: bytes) -> QvapUsage:
    """Decode a command-0x04 reply: two uint24 minute counters."""
    _check(frame, CMD_USAGE, _USAGE_MIN)
    return QvapUsage(
        heater_minutes=int.from_bytes(frame[1:4], "little"),
        charging_minutes=int.from_bytes(frame[4:7], "little"),
    )


def parse_identity(frame: bytes) -> QvapIdentity:
    """Decode a command-0x05 reply: prefix + serial, optional colour."""
    _check(frame, CMD_IDENTITY, _IDENTITY_MIN)
    serial = (frame[15:17] + frame[9:15]).decode("utf-8", "replace").strip("\x00 ")
    color = frame[18] if len(frame) >= _IDENTITY_WITH_COLOR else None
    return QvapIdentity(serial=serial, color_index=color)


def parse_settings6(frame: bytes) -> QvapSettings:
    """Decode a command-0x06 reply."""
    _check(frame, CMD_SETTINGS, SETTINGS6_LENGTH)
    return QvapSettings(
        brightness=frame[2],
        vibration=frame[5] != 0,
        boost_timeout_disabled=frame[6] != 0,
    )


def parse_advertising(frame: bytes) -> bool:
    """Decode a command-0x1D reply: whether find-my-device mode is active."""
    _check(frame, CMD_ADVERTISING, _ADVERTISING_MIN)
    return bool(frame[1] & 0x10)
