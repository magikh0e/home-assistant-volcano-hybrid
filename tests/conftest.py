"""Fixtures for the Volcano Hybrid tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from habluetooth import get_manager
from homeassistant.config_entries import ConfigEntryState

from custom_components.volcano_hybrid.volcano_ble import DeviceFamily

from . import FakeDevice, make_config_entry

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture
async def enable_bluetooth(enable_bluetooth: None) -> AsyncGenerator[None]:
    """
    Augment the upstream fixture to cancel the device-expiry timer.

    The bluetooth integration discards the cancel callback returned by
    HaScanner.async_setup(), and HaScanner.async_stop() does not cancel the
    self-rescheduling expire-devices timer either, so unloading the bluetooth
    config entry leaves a timer behind that trips the lingering-timer check.
    """
    yield
    for scanner in get_manager().async_current_scanners():
        scanner._unsetup()  # noqa: SLF001


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent the integration from actually being set up."""
    with patch(
        "custom_components.volcano_hybrid.async_setup_entry", return_value=True
    ) as mock:
        yield mock


@pytest.fixture
def device_family(request: pytest.FixtureRequest) -> DeviceFamily:
    """Pick the family the fake speaks; parametrize indirectly for another."""
    return getattr(request, "param", DeviceFamily.VOLCANO_HYBRID)


@pytest.fixture
def mock_volcano(device_family: DeviceFamily) -> Generator[FakeDevice]:
    """Replace the protocol layer with an in-memory fake."""
    fake = FakeDevice(device_family)
    with patch(
        "custom_components.volcano_hybrid.coordinator.create_device",
        side_effect=fake.attach,
    ):
        yield fake


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Ensure all entities are enabled in the entity registry."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
        new_callable=PropertyMock,
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_volcano: FakeDevice,
    enable_bluetooth: None,
    device_family: DeviceFamily,
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the integration with a mocked device."""
    entry = make_config_entry(device_family)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    yield entry

    if entry.state is ConfigEntryState.LOADED:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
