"""
Compare the firmware version recorded in the integration against the vendor's.

Storz & Bickel's web app asks their server which firmware is current before it
offers an update. This script asks the same endpoint on a schedule so the
integration never has to, and reports when the answer stops matching
`LATEST_KNOWN_FIRMWARE` or when the endpoint itself changes shape.

Run by `.github/workflows/firmware-check.yml`. Uses only the standard library
so the workflow needs no dependency install. Exits non-zero when it has
something to report, and writes `status`, `title` and `body` to $GITHUB_OUTPUT.
"""

from __future__ import annotations

import ast
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Final

# The endpoint each family's vendor app flow posts to, with the body that asks
# only for the current version numbers. ("version=false" on the Hybrid endpoint
# would return the firmware binary, which this check has no business
# downloading.) Keys are the DeviceFamily values used in `LATEST_KNOWN_FIRMWARE`.
ENDPOINTS: Final[dict[str, tuple[str, dict[str, str]]]] = {
    "volcano_hybrid": (
        "https://app.storz-bickel.com/firmwareHybrid",
        {"version": "true"},
    ),
    "venty": (
        "https://app.storz-bickel.com/firmware",
        {"device": "Venty", "action": "version", "serial": ""},
    ),
    "veazy": (
        "https://app.storz-bickel.com/firmware",
        {"device": "Veazy", "action": "version", "serial": ""},
    ),
}
FAMILY_LABELS: Final = {
    "volcano_hybrid": "Volcano Hybrid",
    "venty": "Venty",
    "veazy": "Veazy",
}
TIMEOUT_SECONDS: Final = 30
HTTP_OK: Final = 200
VALID: Final = 1
EXCERPT_CHARS: Final = 2000

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
FIRMWARE_MODULE: Final = (
    REPO_ROOT / "custom_components" / "volcano_hybrid" / "firmware.py"
)
CONSTANT_NAME: Final = "LATEST_KNOWN_FIRMWARE"

EXPECTED_SHAPE: Final = (
    "[{'valid': 1, 'majorApplication': int, 'minorApplication': int}]"
)


class CheckError(Exception):
    """A problem worth opening an issue about."""

    def __init__(self, status: str, title: str, body: str) -> None:
        """Record how the check failed."""
        super().__init__(title)
        self.status = status
        self.title = title
        self.body = body


def _excerpt(raw: str) -> str:
    """Quote a response body for an issue, bounded so it stays readable."""
    return f"```\n{raw[:EXCERPT_CHARS]}\n```"


def _schema_change(raw: str, family: str) -> CheckError:
    """Report that the endpoint no longer returns what this script expects."""
    body = (
        f"The response no longer looks like `{EXPECTED_SHAPE}`. The integration "
        "does not call this endpoint at runtime, so nothing is broken for "
        "users, but this check cannot tell whether new firmware shipped until "
        f"it is taught the new format.\n\nResponse was:\n\n{_excerpt(raw)}"
    )
    title = f"{FAMILY_LABELS[family]} firmware endpoint changed shape"
    return CheckError("schema-change", title, body)


def _endpoint_error(title: str, body: str) -> CheckError:
    """Report that the endpoint could not be reached or refused to answer."""
    return CheckError("endpoint-error", title, body)


def _format(version: tuple[int, int]) -> str:
    """Render a version the way Storz & Bickel write it."""
    return f"V{version[0]:02d}.{version[1]:02d}"


def read_recorded_versions() -> dict[str, tuple[int, int] | None]:
    """
    Read LATEST_KNOWN_FIRMWARE out of the integration.

    Parsed rather than imported so this runs without Home Assistant installed.
    A family with no verified firmware yet is recorded as None.
    """
    tree = ast.parse(FIRMWARE_MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            first = node.targets[0]
            target = first.id if isinstance(first, ast.Name) else None
        if target == CONSTANT_NAME and node.value is not None:
            recorded = ast.literal_eval(node.value)
            return {
                family: None if version is None else (int(version[0]), int(version[1]))
                for family, version in recorded.items()
            }
    message = f"{CONSTANT_NAME} not found in {FIRMWARE_MODULE}"
    raise LookupError(message)


def fetch_published_version(family: str) -> tuple[int, int]:
    """Ask the vendor endpoint which firmware is current for a family."""
    endpoint, request_body = ENDPOINTS[family]
    label = FAMILY_LABELS[family]
    data = urllib.parse.urlencode(request_body).encode()
    request = urllib.request.Request(endpoint, data=data, method="POST")  # noqa: S310
    try:
        # The endpoints are fixed https literals, so the scheme cannot be
        # attacker controlled; S310 is about dynamic URLs.
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            status = response.status
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        title = f"{label} firmware endpoint is unreachable"
        body = f"`POST {endpoint}` failed: `{err}`."
        raise _endpoint_error(title, body) from err

    if status != HTTP_OK:
        title = f"{label} firmware endpoint returned an error"
        body = f"`POST {endpoint}` responded with HTTP {status}."
        raise _endpoint_error(title, body)
    return _parse_response(raw, family)


def _decode(raw: str, family: str) -> dict[str, Any]:
    """Pull the single result object out of the response body."""
    try:
        payload = json.loads(raw)
        entry = payload[0]
    except (ValueError, TypeError, LookupError) as err:
        raise _schema_change(raw, family) from err
    if not isinstance(entry, dict):
        raise _schema_change(raw, family)
    return entry


def _parse_response(raw: str, family: str = "volcano_hybrid") -> tuple[int, int]:
    """Pull the version out of the endpoint's JSON, or report a shape change."""
    entry = _decode(raw, family)

    try:
        valid = int(entry["valid"])
    except (ValueError, TypeError, LookupError) as err:
        raise _schema_change(raw, family) from err
    if valid != VALID:
        title = (
            f"{FAMILY_LABELS[family]} firmware endpoint reported an invalid response"
        )
        body = f"The endpoint returned `valid != {VALID}`:\n\n{_excerpt(raw)}"
        raise _endpoint_error(title, body)

    try:
        return (int(entry["majorApplication"]), int(entry["minorApplication"]))
    except (ValueError, TypeError, LookupError) as err:
        raise _schema_change(raw, family) from err


def build_outdated_report(
    family: str, recorded: tuple[int, int] | None, published: tuple[int, int]
) -> CheckError:
    """Describe a version mismatch and what to do about it."""
    label = FAMILY_LABELS[family]
    if recorded is None:
        situation = (
            f"Storz & Bickel publish **{_format(published)}** for the {label}, "
            "and the integration records no version for this family yet.\n\n"
            "Users are not affected: the update entity reports no latest "
            "version for the device until one is recorded, and the "
            "integration never contacts this endpoint itself.\n\n"
        )
        action = (
            f"3. Record `{published}` for `{family}` in `{CONSTANT_NAME}` once "
            "verified, and note the supported firmware in `CHANGELOG.md`.\n"
        )
    else:
        direction = "newer than" if published > recorded else "different from"
        situation = (
            f"Storz & Bickel now publish **{_format(published)}** for the "
            f"{label}, which is {direction} the **{_format(recorded)}** "
            "recorded in `custom_components/volcano_hybrid/firmware.py`.\n\n"
            "Users are not affected until this is acted on: the integration "
            f"reports devices as up to date at {_format(recorded)} and never "
            "contacts this endpoint itself.\n\n"
        )
        action = (
            f"3. Bump `{family}` in `{CONSTANT_NAME}` to `{published}` and note "
            "the supported firmware in `CHANGELOG.md`.\n"
        )
    body = (
        f"{situation}To close this out:\n\n"
        "1. Flash the new firmware with the official web app "
        "(<https://app.storz-bickel.com/>).\n"
        "2. Check the integration still reads and controls the device — in "
        "particular the status registers, since new firmware can move bits.\n"
        f"{action}"
    )
    return CheckError(
        "outdated",
        f"{label} firmware {_format(published)} is available",
        body,
    )


def write_outputs(status: str, title: str, body: str) -> None:
    """Publish the result to the workflow, when running inside one."""
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return
    with Path(output).open("a", encoding="utf-8") as handle:
        handle.write(f"status={status}\n")
        handle.write(f"title={title}\n")
        handle.write(f"body<<FIRMWARE_CHECK_EOF\n{body}\nFIRMWARE_CHECK_EOF\n")


def _check_family(family: str, recorded: tuple[int, int] | None) -> None:
    """Raise a CheckError when a family's published firmware needs attention."""
    published = fetch_published_version(family)
    if published != recorded:
        raise build_outdated_report(family, recorded, published)


def main() -> int:
    """Run the check for every family and report the outcome."""
    recorded = read_recorded_versions()
    failures: list[tuple[str, CheckError]] = []
    for family in ENDPOINTS:
        try:
            _check_family(family, recorded.get(family))
        except CheckError as failure:
            print(f"::warning::{failure.title}")
            print(failure.body)
            failures.append((family, failure))
        else:
            print(f"{FAMILY_LABELS[family]} firmware matches the vendor endpoint.")

    if failures:
        # One issue per run. The status carries the family, and the workflow
        # dedupes on it, so each family and kind of problem is raised in turn.
        family, failure = failures[0]
        write_outputs(f"{family}-{failure.status}", failure.title, failure.body)
        return 1

    write_outputs("ok", "", "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
