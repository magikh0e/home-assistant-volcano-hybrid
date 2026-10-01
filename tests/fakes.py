"""Fakes of the bleak client shared by the protocol-layer tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import VOLCANO_ADDRESS

if TYPE_CHECKING:
    from collections.abc import Callable


class FakeCharacteristic:
    """A GATT characteristic that only knows its uuid."""

    def __init__(self, uuid: str) -> None:
        """Initialize the characteristic."""
        self.uuid = uuid


class FakeService:
    """A GATT service handing out characteristics."""

    def __init__(self, missing: set[str]) -> None:
        """Initialize the service."""
        self.missing = missing

    def get_characteristic(self, uuid: str) -> FakeCharacteristic | None:
        """Get a characteristic by uuid, returning None when the device lacks it."""
        return None if uuid in self.missing else FakeCharacteristic(uuid)


class FakeServices:
    """A GATT service collection."""

    def __init__(self, missing: set[str]) -> None:
        """Initialize the collection."""
        self.missing = missing

    def get_service(self, uuid: str) -> FakeService:
        """Get a service by uuid."""
        return FakeService(self.missing)


class FakeBleakClient:
    """A BleakClient that serves canned characteristic values."""

    def __init__(
        self,
        values: dict[str, bytes],
        missing: set[str] | None = None,
        address: str = VOLCANO_ADDRESS,
    ) -> None:
        """Initialize the client, optionally without some characteristics."""
        self.values = values
        self.written: list[tuple[str, bytes]] = []
        self.notify_callbacks: dict[str, Callable[..., Any]] = {}
        self.is_connected = True
        self.address = address
        self.services = FakeServices(missing or set())

    async def read_gatt_char(self, char: FakeCharacteristic) -> bytearray:
        """Read a characteristic."""
        return bytearray(self.values[char.uuid])

    async def write_gatt_char(self, char: FakeCharacteristic, value: bytearray) -> None:
        """Record a write."""
        self.written.append((char.uuid, bytes(value)))

    async def start_notify(
        self, char: FakeCharacteristic, callback: Callable[..., Any]
    ) -> None:
        """Record a notification subscription."""
        self.notify_callbacks[char.uuid] = callback

    async def disconnect(self) -> None:
        """Disconnect the client."""
        self.is_connected = False
