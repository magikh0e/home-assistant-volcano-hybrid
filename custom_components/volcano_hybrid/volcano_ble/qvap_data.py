"""State of a Venty or Veazy, filled from the frames in qvap_frames."""

from __future__ import annotations

from typing import ClassVar

from .const import (
    PORTABLE_MAX_READING,
    PORTABLE_MAX_TEMP,
    PORTABLE_MIN_DISPLAY_TEMP,
    PORTABLE_MIN_TEMP,
    DeviceFamily,
    VolcanoSensor,
)
from .data import DeviceData, VolcanoHybridDataStatusProvider
from .qvap_frames import (
    BIT2_PERMANENT_BLUETOOTH,
    BIT_BOOST_VISUALIZATION,
    BIT_CHARGE_LIMIT,
    BIT_CHARGE_OPTIMIZATION,
    BIT_FAHRENHEIT,
    BIT_SETPOINT_REACHED,
    BIT_TARGET_CHANGED,
    HEATER_MODE_BOOST,
    HEATER_MODE_OFF,
    HEATER_MODE_SUPERBOOST,
    QvapFirmware,
    QvapIdentity,
    QvapSettings,
    QvapStatus,
    QvapUsage,
)

HEATER_MODE_OPTIONS = ["off", "heating", "boost", "superboost"]
# Spec §3.3: 2 blue, 3 pink, 4 orange, anything else black.
COLOR_OPTIONS = ["black", "blue", "pink", "orange"]
_COLOR_BY_INDEX = {2: "blue", 3: "pink", 4: "orange"}

_SHARED_CAPABILITIES = frozenset(
    {
        VolcanoSensor.VOLCANO,
        VolcanoSensor.FIRMWARE,
        VolcanoSensor.BOOST_TEMP,
        VolcanoSensor.SUPERBOOST_TEMP,
        VolcanoSensor.BRIGHTNESS,
        VolcanoSensor.SHOWING_CELSIUS,
        VolcanoSensor.VIBRATION,
        VolcanoSensor.CHARGE_OPTIMIZATION,
        VolcanoSensor.CHARGE_LIMIT,
        VolcanoSensor.BOOST_VISUALIZATION,
        VolcanoSensor.BOOST_TIMEOUT_DISABLED,
        VolcanoSensor.AUTO_CONNECT,
        VolcanoSensor.BATTERY,
        VolcanoSensor.AUTO_OFF_COUNTDOWN,
        VolcanoSensor.HEATER_MODE,
        VolcanoSensor.HEAT_TIME,
        VolcanoSensor.CHARGING_TIME,
        VolcanoSensor.RSSI,
        VolcanoSensor.CONNECTED_ADDR,
        VolcanoSensor.AT_TEMPERATURE,
        VolcanoSensor.HEATER_ACTIVE,
        VolcanoSensor.CHARGING,
        VolcanoSensor.BOOST_MODE,
        VolcanoSensor.SUPERBOOST_MODE,
        VolcanoSensor.TARGET_CHANGED_ON_DEVICE,
        VolcanoSensor.BOOTLOADER_MODE,
        VolcanoSensor.CONNECTED,
        VolcanoSensor.RECONNECT,
        VolcanoSensor.DELAYED_RECONNECT,
        VolcanoSensor.FIND_DEVICE,
    }
)


class QvapData(DeviceData):
    """Data object for the Venty/Veazy protocol family."""

    MIN_TEMP = PORTABLE_MIN_TEMP
    MAX_TEMP = PORTABLE_MAX_TEMP
    MAX_READING = PORTABLE_MAX_READING
    MIN_DISPLAY_TEMP = PORTABLE_MIN_DISPLAY_TEMP
    # The Veazy reports the visualisation bit inverted (spec §2.3).
    INVERT_BOOST_VISUALIZATION: ClassVar[bool] = False

    def __init__(self, device: VolcanoHybridDataStatusProvider) -> None:
        """Initialize the Qvap fields."""
        super().__init__(device)
        self.battery: int | None = None
        self.charging: bool | None = None
        self.boost_temp: int | None = None
        self.superboost_temp: int | None = None
        self.heater_mode: int | None = None
        self.auto_off_countdown: int | None = None
        self.showing_celsius: bool | None = None
        self.charge_optimization: bool | None = None
        self.charge_limit: bool | None = None
        self.boost_visualization: bool | None = None
        self.permanent_bluetooth: bool | None = None
        self.target_changed_on_device: bool | None = None
        self.brightness: int | None = None
        self.vibration: bool | None = None
        self.boost_timeout_disabled: bool | None = None
        self.heat_time: int | None = None
        self.charging_time: int | None = None
        self.color: str | None = None
        # None until the firmware reply (spec §3.1) has said which mode it is in.
        self.bootloader_mode: bool | None = None
        self.invalid_application: bool | None = None
        self.invalid_bootloader: bool | None = None
        self.find_mode: bool | None = None

    @property
    def boost_mode(self) -> bool | None:
        """Whether the heater is in boost mode."""
        if self.heater_mode is None:
            return None
        return self.heater_mode == HEATER_MODE_BOOST

    @property
    def superboost_mode(self) -> bool | None:
        """Whether the heater is in superboost mode."""
        if self.heater_mode is None:
            return None
        return self.heater_mode == HEATER_MODE_SUPERBOOST

    @property
    def heater_mode_name(self) -> str | None:
        """The heater mode as an enum state."""
        if self.heater_mode is None or self.heater_mode >= len(HEATER_MODE_OPTIONS):
            return None
        return HEATER_MODE_OPTIONS[self.heater_mode]

    @property
    def permanent_bluetooth_enabled(self) -> bool | None:
        """The same setting under the read-only key the Venty exposes it as."""
        return self.permanent_bluetooth

    def apply_status(self, status: QvapStatus) -> None:
        """Take over a command-0x01 reply (spec §2.1, §2.3)."""
        self.current_temp = status.current_temp
        self.set_temp = status.target_temp
        self.boost_temp = status.boost
        self.superboost_temp = status.superboost
        self.battery = status.battery
        self.auto_off_countdown = status.countdown
        self.heater_mode = status.heater_mode
        self.heater = status.heater_mode != HEATER_MODE_OFF
        self.charging = status.charging
        bits = status.settings
        self.showing_celsius = not bits & BIT_FAHRENHEIT
        self.at_temperature = bool(bits & BIT_SETPOINT_REACHED)
        self.charge_optimization = bool(bits & BIT_CHARGE_OPTIMIZATION)
        self.target_changed_on_device = bool(bits & BIT_TARGET_CHANGED)
        self.charge_limit = bool(bits & BIT_CHARGE_LIMIT)
        visualization = bool(bits & BIT_BOOST_VISUALIZATION)
        self.boost_visualization = (
            not visualization if self.INVERT_BOOST_VISUALIZATION else visualization
        )
        if status.settings2 is not None:
            self.permanent_bluetooth = bool(status.settings2 & BIT2_PERMANENT_BLUETOOTH)

    def apply_firmware(self, firmware: QvapFirmware) -> None:
        """Take over a command-0x02 reply (spec §3.1)."""
        self.firmware_version = firmware.firmware_version
        self.bootloader_version = firmware.bootloader_version
        self.bootloader_mode = not firmware.application_running
        self.invalid_application = firmware.invalid_application
        self.invalid_bootloader = firmware.invalid_bootloader

    def forget_mode(self) -> None:
        """Treat the mode as unknown until the next firmware reply (spec §3.1)."""
        self.bootloader_mode = None

    def apply_usage(self, usage: QvapUsage) -> None:
        """Take over a command-0x04 reply (spec §3.2)."""
        self.heat_time = usage.heater_minutes
        self.charging_time = usage.charging_minutes

    def apply_identity(self, identity: QvapIdentity) -> None:
        """Take over a command-0x05 reply (spec §3.3)."""
        self.serial_number = identity.serial
        if identity.color_index is not None:
            self.color = _COLOR_BY_INDEX.get(identity.color_index, "black")

    def apply_settings6(self, settings: QvapSettings) -> None:
        """Take over a command-0x06 reply (spec §3.4)."""
        self.brightness = settings.brightness
        self.vibration = settings.vibration
        self.boost_timeout_disabled = settings.boost_timeout_disabled


class VentyData(QvapData):
    """A Venty: permanent Bluetooth is read-only, no colour."""

    family = DeviceFamily.VENTY
    capabilities = _SHARED_CAPABILITIES | {VolcanoSensor.PERMANENT_BLUETOOTH_ENABLED}


class VeazyData(QvapData):
    """A Veazy: writable permanent Bluetooth, inverted visualisation bit, colour."""

    family = DeviceFamily.VEAZY
    INVERT_BOOST_VISUALIZATION = True
    capabilities = _SHARED_CAPABILITIES | {
        VolcanoSensor.PERMANENT_BLUETOOTH,
        VolcanoSensor.COLOR,
    }
