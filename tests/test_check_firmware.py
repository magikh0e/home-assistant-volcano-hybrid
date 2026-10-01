"""
Tests for the scheduled firmware endpoint check.

The check is the only thing that notices new firmware, so its failure paths
matter: a silently broken check looks exactly like "no new firmware".
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.volcano_hybrid.firmware import LATEST_KNOWN_FIRMWARE

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from types import ModuleType

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_firmware.py"


def _load() -> ModuleType:
    """Import the script by path; scripts/ is deliberately not a package."""
    spec = importlib.util.spec_from_file_location("check_firmware", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_firmware = _load()

_RECORDED = LATEST_KNOWN_FIRMWARE["volcano_hybrid"]
assert _RECORDED is not None
LATEST: tuple[int, int] = _RECORDED


def _response(
    family: str = "volcano_hybrid",
    version: tuple[int, int] = LATEST,
    **overrides: Any,
) -> str:
    """Build a response body shaped like a family's vendor endpoint."""
    payload: dict[str, Any] = {
        "valid": 1,
        "majorApplication": version[0],
        "minorApplication": version[1],
    }
    if family != "volcano_hybrid":
        payload |= {"majorBootloader": 1, "minorBootloader": 0}
    payload.update(overrides)
    return json.dumps([payload])


def test_reads_the_versions_recorded_in_the_integration() -> None:
    """The constant is read from source without importing Home Assistant."""
    assert check_firmware.read_recorded_versions() == LATEST_KNOWN_FIRMWARE


def test_every_recorded_family_has_an_endpoint() -> None:
    """A family added to the constant cannot be silently left unchecked."""
    assert set(check_firmware.ENDPOINTS) == set(LATEST_KNOWN_FIRMWARE)


@pytest.mark.parametrize("family", ["volcano_hybrid", "venty", "veazy"])
def test_parses_a_healthy_response(family: str) -> None:
    """A well-formed response yields the published version."""
    raw = _response(family, (1, 9))
    assert check_firmware._parse_response(raw, family) == (1, 9)  # noqa: SLF001


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        "{}",
        "[]",
        '[{"valid": 1}]',
        '[{"valid": 1, "majorApplication": "one", "minorApplication": 3}]',
        '[{"valid": 1, "applicationVersion": "1.3"}]',
    ],
)
def test_reports_a_schema_change(raw: str) -> None:
    """Anything that is not the expected shape is flagged, not guessed at."""
    with pytest.raises(check_firmware.CheckError) as err:
        check_firmware._parse_response(raw)  # noqa: SLF001
    assert err.value.status == "schema-change"


def test_reports_an_invalid_response() -> None:
    """The endpoint's own "not valid" answer is a failure, not a version."""
    with pytest.raises(check_firmware.CheckError) as err:
        check_firmware._parse_response(_response(valid=0))  # noqa: SLF001
    assert err.value.status == "endpoint-error"


def test_outdated_report_names_both_versions() -> None:
    """The issue body says what shipped, what is recorded, and what to do."""
    published = (LATEST[0], LATEST[1] + 1)
    failure = check_firmware.build_outdated_report("volcano_hybrid", LATEST, published)

    assert failure.status == "outdated"
    assert "Volcano Hybrid" in failure.title
    assert check_firmware._format(published) in failure.title  # noqa: SLF001
    assert check_firmware._format(published) in failure.body  # noqa: SLF001
    assert check_firmware._format(LATEST) in failure.body  # noqa: SLF001
    assert "LATEST_KNOWN_FIRMWARE" in failure.body


def test_reports_unknown_recorded_version_as_outdated() -> None:
    """A family with nothing recorded still raises the published version."""
    failure = check_firmware.build_outdated_report("venty", None, (1, 9))

    assert failure.status == "outdated"
    assert "Venty" in failure.title
    assert "V01.09" in failure.title
    assert "records no version for this family" in failure.body
    assert "once verified" in failure.body


def _fake_fetch(
    responses: Mapping[str, tuple[int, int] | Exception],
) -> Callable[[str], tuple[int, int]]:
    """Stand in for the network: answer per family, never touch a socket."""

    def fetch(family: str) -> tuple[int, int]:
        result = responses[family]
        if isinstance(result, Exception):
            raise result
        return result

    return fetch


def test_main_is_quiet_when_every_family_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recorded versions equal to the published ones report ok."""
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    versions = {"volcano_hybrid": LATEST, "venty": (1, 9), "veazy": (1, 9)}
    monkeypatch.setattr(check_firmware, "read_recorded_versions", lambda: versions)
    monkeypatch.setattr(
        check_firmware, "fetch_published_version", _fake_fetch(versions)
    )

    assert check_firmware.main() == 0
    assert "status=ok\n" in output.read_text(encoding="utf-8")


def test_main_labels_the_first_failure_with_its_family(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The status carries the family so issues dedupe per family and kind."""
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(
        check_firmware,
        "read_recorded_versions",
        lambda: {"volcano_hybrid": LATEST, "venty": None, "veazy": None},
    )
    monkeypatch.setattr(
        check_firmware,
        "fetch_published_version",
        _fake_fetch(
            {
                "volcano_hybrid": LATEST,
                "venty": (1, 9),
                "veazy": check_firmware._endpoint_error("down", "body"),  # noqa: SLF001
            }
        ),
    )

    assert check_firmware.main() == 1
    written = output.read_text(encoding="utf-8")
    assert "status=venty-outdated\n" in written
    assert "veazy" not in written.split("body<<")[0]


def test_writes_workflow_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The workflow reads status/title/body back out of $GITHUB_OUTPUT."""
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    check_firmware.write_outputs("outdated", "A title", "line one\nline two")

    written = output.read_text(encoding="utf-8")
    assert "status=outdated\n" in written
    assert "title=A title\n" in written
    # A multi-line body has to use the delimiter form or the workflow breaks.
    assert (
        "body<<FIRMWARE_CHECK_EOF\nline one\nline two\nFIRMWARE_CHECK_EOF\n" in written
    )


def test_writing_outputs_is_a_no_op_outside_a_workflow() -> None:
    """Running the script by hand should not need GITHUB_OUTPUT set."""
    check_firmware.write_outputs("ok", "", "")
