"""Constants for the VolcanoBLE."""

from enum import StrEnum

VOLCANO_HYBRID_MIN_TEMP = 0
VOLCANO_HYBRID_MAX_TEMP = 230

# The block temperature below which the device blanks its display again after
# the heater is switched off, used to decide when a cooldown has ended. The
# device does not report the state of its display, so this cannot be read back
# and is not measured here: it is what owners observe, and it lines up with the
# lowest temperature the device can be set to. Kept separate from that limit
# anyway, because they are two different facts that happen to share a value.
VOLCANO_HYBRID_DISPLAY_OFF_TEMP = 40


class DeviceFamily(StrEnum):
    """The Storz & Bickel device families this integration speaks to."""

    VOLCANO_HYBRID = "volcano_hybrid"
    # Crafty and Crafty+ share a protocol; the model is told apart by the
    # firmware major version after connecting (CRAFTY_BLE_SPEC.md §6).
    CRAFTY = "crafty"
    VENTY = "venty"
    VEAZY = "veazy"


# How each family is named in the device registry until it says otherwise.
FAMILY_MODEL_NAME: dict[DeviceFamily, str] = {
    DeviceFamily.VOLCANO_HYBRID: "Volcano Hybrid",
    DeviceFamily.CRAFTY: "Crafty",
    DeviceFamily.VENTY: "Venty",
    DeviceFamily.VEAZY: "Veazy",
}

# Portable devices: the app clamps the target to 40-210 °C for both families
# (CRAFTY_BLE_SPEC.md §3, VENTY_BLE_SPEC.md §5).
PORTABLE_MIN_TEMP = 0
PORTABLE_MAX_TEMP = 210
PORTABLE_MIN_DISPLAY_TEMP = 40


class VolcanoSensor(StrEnum):
    """Volcano sensor types."""

    VOLCANO = "volcano"
    FIRMWARE = "firmware"
    CURRENT_AUTO_OFF_TIME = "current_auto_off_time"
    CURRENT_ON_TIME = "current_on_time"
    HEAT_TIME = "heat_time"
    SHUT_OFF = "shut_off"
    LED_BRIGHTNESS = "led_brightness"
    AUTO_SHUTDOWN = "auto_shutdown"
    AT_TEMPERATURE = "at_temperature"
    HEATER_ACTIVE = "heater"
    PUMP_ACTIVE = "fan"
    ACTUATOR_FAULT = "actuator_fault"
    PRV1_ERROR = "prv1_error"
    SHOWING_CELSIUS = "showing_celsius"
    DISPLAY_ON_COOLING = "display_on_cooling"
    SERVICE_MODE = "service_mode"
    PRV2_ERROR = "prv2_error"
    VIBRATION = "vibration"
    RECONNECT = "reconnect"
    DELAYED_RECONNECT = "delayed_reconnect"
    AUTO_CONNECT = "auto_connect"
    CONNECTED = "connected"
    RSSI = "rssi"
    CONNECTED_ADDR = "connected_addr"
    MAINS_VOLTAGE = "mains_voltage"
    PRJ1 = "prj1"
    PRJ2 = "prj2"
    PRJ3 = "prj3"
    PRJ4 = "prj4"
    PRJ5 = "prj5"
    HIST1 = "hist1"
    HIST2 = "hist2"
    LAST_FAULT = "last_fault"
