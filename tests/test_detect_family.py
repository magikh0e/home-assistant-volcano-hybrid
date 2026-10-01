"""Tests for telling the device families apart from their advertisements."""

from __future__ import annotations

import pytest

from custom_components.volcano_hybrid.volcano_ble.const import (
    CRAFTY_SERVICE_UUIDS,
    QVAP_SERVICE_UUID,
    DeviceFamily,
    detect_family,
    is_supported,
)

from . import CRAFTY_NAME, VEAZY_NAME, VENTY_NAME, VOLCANO_NAME, make_service_info


@pytest.mark.parametrize(
    ("name", "manufacturer_id", "service_uuids", "expected"),
    [
        (VOLCANO_NAME, 1736, [], DeviceFamily.VOLCANO_HYBRID),
        # A Volcano needs the manufacturer id: the name alone is not enough.
        (VOLCANO_NAME, 76, [], None),
        (VENTY_NAME, 76, [], DeviceFamily.VENTY),
        (VEAZY_NAME, 76, [], DeviceFamily.VEAZY),
        # The Qvap service without a known name is refused, not guessed.
        ("S&B XX000000", 76, [QVAP_SERVICE_UUID], None),
        (CRAFTY_NAME, 76, [], DeviceFamily.CRAFTY),
        ("Storz&Bickel", 76, [], DeviceFamily.CRAFTY),
        ("Unnamed", 76, [CRAFTY_SERVICE_UUIDS[0]], DeviceFamily.CRAFTY),
        ("OTHER DEVICE", 76, [], None),
        ("S&B CRAFTY 123", 1736, [], None),
    ],
)
def test_detect_family(
    name: str,
    manufacturer_id: int,
    service_uuids: list[str],
    expected: DeviceFamily | None,
) -> None:
    """Each family is recognised by what its advertisement carries."""
    info = make_service_info(
        name=name, manufacturer_id=manufacturer_id, service_uuids=service_uuids
    )
    assert detect_family(info) is expected
    assert is_supported(info) is (expected is not None)


def test_detect_family_without_a_name() -> None:
    """A nameless advertisement is only a Crafty if it carries the service."""
    info = make_service_info(name="", manufacturer_id=76)
    assert detect_family(info) is None
