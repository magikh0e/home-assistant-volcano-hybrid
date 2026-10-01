"""Entity behaviour specific to the Venty/Veazy family."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.components.number import (
    ATTR_VALUE,
    SERVICE_SET_VALUE,
)
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)

from custom_components.volcano_hybrid.volcano_ble import DeviceFamily

from . import FakeDevice, get_entity_id

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


def _state(hass: HomeAssistant, platform: str, key: str) -> str:
    """Return the state of one entity by its key."""
    state = hass.states.get(get_entity_id(hass, platform, key))
    assert state is not None
    return state.state


@pytest.mark.parametrize("device_family", [DeviceFamily.VENTY], indirect=True, ids=str)
async def test_heater_mode_and_charging(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    init_integration: MockConfigEntry,
    mock_volcano: FakeDevice,
) -> None:
    """The mode name, charging, bootloader and permanent-Bluetooth state show."""
    mock_volcano.connected = True
    data = mock_volcano.data
    data.heater_mode = 3
    data.charging = True
    data.bootloader_mode = False
    data.permanent_bluetooth = True
    mock_volcano.data_updated()
    await hass.async_block_till_done()

    assert _state(hass, "sensor", "heater_mode") == "superboost"
    assert _state(hass, "binary_sensor", "superboost_mode") == STATE_ON
    assert _state(hass, "binary_sensor", "charging") == STATE_ON
    assert _state(hass, "binary_sensor", "bootloader_mode") == STATE_OFF
    assert _state(hass, "binary_sensor", "permanent_bluetooth_enabled") == STATE_ON


@pytest.mark.parametrize("device_family", [DeviceFamily.VEAZY], indirect=True, ids=str)
async def test_veazy_colour_and_permanent_bluetooth_switch(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    init_integration: MockConfigEntry,
    mock_volcano: FakeDevice,
) -> None:
    """The Veazy reports its colour and lets the permanent-Bluetooth bit be set."""
    mock_volcano.connected = True
    mock_volcano.data.color = "orange"
    mock_volcano.data.permanent_bluetooth = False
    mock_volcano.data_updated()
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "color") == "orange"
    entity_id = get_entity_id(hass, "switch", "permanent_bluetooth")
    assert _state(hass, "switch", "permanent_bluetooth") == STATE_OFF
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert ("permanent_bluetooth", True) in mock_volcano.commands


@pytest.mark.parametrize("device_family", [DeviceFamily.VENTY], indirect=True, ids=str)
@pytest.mark.parametrize(
    ("key", "value"), [("boost_temp", 12), ("superboost_temp", 25), ("brightness", 4)]
)
async def test_numbers(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    init_integration: MockConfigEntry,
    mock_volcano: FakeDevice,
    key: str,
    value: int,
) -> None:
    """Each number writes through to the device."""
    mock_volcano.connected = True
    mock_volcano.data_updated()
    await hass.async_block_till_done()
    entity_id = get_entity_id(hass, "number", key)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )
    assert (key, value) in mock_volcano.commands


@pytest.mark.parametrize("device_family", [DeviceFamily.VENTY], indirect=True, ids=str)
@pytest.mark.parametrize(
    "key",
    [
        "showing_celsius",
        "vibration",
        "charge_optimization",
        "charge_limit",
        "boost_visualization",
        "boost_timeout_disabled",
    ],
)
async def test_switches(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    init_integration: MockConfigEntry,
    mock_volcano: FakeDevice,
    key: str,
) -> None:
    """Each switch reflects the data and writes through in both directions."""
    mock_volcano.connected = True
    setattr(mock_volcano.data, key, True)
    mock_volcano.data_updated()
    await hass.async_block_till_done()
    entity_id = get_entity_id(hass, "switch", key)
    assert _state(hass, "switch", key) == STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert (key, False) in mock_volcano.commands
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert (key, True) in mock_volcano.commands
