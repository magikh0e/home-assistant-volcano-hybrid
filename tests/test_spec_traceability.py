"""Every UUID and mask in the new protocol modules must be in its spec document."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
BLE = ROOT / "custom_components" / "volcano_hybrid" / "volcano_ble"
UUID_PREFIX = re.compile(
    r'"([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"'
)
# crafty.py builds its UUIDs as `"00000011" + _BASE`, so the full-UUID pattern
# above never sees them.
CONCAT_PREFIX = re.compile(r'"([0-9a-f]{8})"\s*\+\s*_BASE\b')
BASE_SUFFIX = re.compile(r'^_BASE = "(-[0-9a-f-]+)"', re.MULTILINE)
HEX_MASK = re.compile(r"= (0x[0-9A-Fa-f]{2,4})\b")


@pytest.mark.parametrize(
    ("module", "spec"),
    [
        ("crafty.py", "CRAFTY_BLE_SPEC.md"),
        ("crafty_data.py", "CRAFTY_BLE_SPEC.md"),
        ("qvap.py", "VENTY_BLE_SPEC.md"),
        ("qvap_frames.py", "VENTY_BLE_SPEC.md"),
    ],
)
def test_constants_are_documented(module: str, spec: str) -> None:
    """Each UUID and mask a module defines appears in the spec it implements."""
    source = (BLE / module).read_text(encoding="utf-8")
    document = (ROOT / spec).read_text(encoding="utf-8").lower()

    prefixes = UUID_PREFIX.findall(source) + CONCAT_PREFIX.findall(source)
    masks = HEX_MASK.findall(source)
    # A module that yields nothing would pass vacuously.
    assert prefixes or masks, f"{module}: found no UUID or mask to check"

    for base in BASE_SUFFIX.findall(source):
        assert base.lower() in document, f"{module}: UUID base {base} is not in {spec}"
    for prefix in prefixes:
        assert prefix in document, f"{module}: UUID {prefix} is not in {spec}"
    for mask in masks:
        # The spec writes 16-bit masks as 0x0010 and byte masks as 0x10.
        assert mask.lower() in document or f"0x{int(mask, 16):04x}" in document, (
            f"{module}: {mask} is not in {spec}"
        )


def test_crafty_uuids_are_actually_extracted() -> None:
    """The concatenated form is covered, so crafty.py cannot pass vacuously."""
    source = (BLE / "crafty.py").read_text(encoding="utf-8")
    assert len(CONCAT_PREFIX.findall(source)) >= 20
    assert BASE_SUFFIX.findall(source) == ["-4c45-4b43-4942-265a524f5453"]
