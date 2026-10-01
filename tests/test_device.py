"""Tests for the device base class and factory."""

from __future__ import annotations

import pytest

from custom_components.volcano_hybrid.volcano_ble.const import DeviceFamily
from custom_components.volcano_hybrid.volcano_ble.device import (
    StorzBickelDevice,
    UnsupportedCommandError,
)
from custom_components.volcano_hybrid.volcano_ble.families import (
    DATA_CLASSES,
    DEVICE_CLASSES,
    create_device,
)
from custom_components.volcano_hybrid.volcano_ble.volcano_ble import VolcanoDevice
from custom_components.volcano_hybrid.volcano_ble.volcano_hybrid_data import (
    VolcanoHybridData,
)


def test_factory_builds_the_volcano() -> None:
    """The Volcano family maps to today's device and data classes."""
    device = create_device(DeviceFamily.VOLCANO_HYBRID, lambda: None, lambda: None)
    assert isinstance(device, VolcanoDevice)
    assert isinstance(device, StorzBickelDevice)
    assert isinstance(device.data, VolcanoHybridData)
    assert device.family is DeviceFamily.VOLCANO_HYBRID
    assert DATA_CLASSES[DeviceFamily.VOLCANO_HYBRID] is VolcanoHybridData
    assert DEVICE_CLASSES[DeviceFamily.VOLCANO_HYBRID] is VolcanoDevice


def test_every_family_has_a_device_and_data_class() -> None:
    """A family without an implementation cannot be configured."""
    for family in DEVICE_CLASSES:
        assert DATA_CLASSES[family].family is family
        assert DEVICE_CLASSES[family].family is family


async def test_base_commands_are_unsupported() -> None:
    """A family that does not override a command refuses it, never sends it."""
    device = create_device(DeviceFamily.VOLCANO_HYBRID, lambda: None, lambda: None)
    with pytest.raises(UnsupportedCommandError):
        await StorzBickelDevice.async_set_boost_temperature(device, 10)
