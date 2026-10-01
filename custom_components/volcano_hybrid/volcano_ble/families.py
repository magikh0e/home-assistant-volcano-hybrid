"""The registry of device families: which class speaks which protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import DeviceFamily
from .crafty import CraftyDevice
from .volcano_ble import VolcanoDevice

if TYPE_CHECKING:
    from collections.abc import Callable

    from .data import DeviceData
    from .device import StorzBickelDevice

DEVICE_CLASSES: dict[DeviceFamily, type[StorzBickelDevice]] = {
    DeviceFamily.VOLCANO_HYBRID: VolcanoDevice,
    DeviceFamily.CRAFTY: CraftyDevice,
}
DATA_CLASSES: dict[DeviceFamily, type[DeviceData]] = {
    family: cls.data_class for family, cls in DEVICE_CLASSES.items()
}


def create_device(
    family: DeviceFamily,
    data_updated: Callable[[], None],
    device_updated: Callable[[], None],
) -> StorzBickelDevice:
    """Build the device class that speaks the family's protocol."""
    return DEVICE_CLASSES[family](data_updated, device_updated)
