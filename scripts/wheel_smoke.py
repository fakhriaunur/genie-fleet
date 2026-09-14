"""Installed-wheel smoke: replay golden + Maya dispatch in one process.

Shared assertion core for ``mise run verify-wheel`` and the CI wheel jobs.
Runs against whatever ``genie_fleet`` is importable (repo checkout or an
installed wheel) with ``GENIE_MODE=mock``:

- ``--expect-pure``: ``NATIVE_AVAILABLE`` is False, the golden fixture is
  byte-identical, and Maya dispatches 2 moved / 6 total.
- ``--expect-native`` (with ``GENIE_NATIVE=1``): the extension is present,
  the golden fixture is still byte-identical, Maya dispatches over the
  native path label, and every outage's native report byte-equals Python.
- ``--check-wheel PATH``: assert the wheel artifact itself carries no
  ``.so`` (``--expect-pure``) or exactly one top-level
  ``genie_fleet_native<EXT_SUFFIX>`` (``--expect-native``).
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN = REPO_ROOT / "tests" / "replay" / "fixtures" / "dispatch_golden.json"
OUTAGES = ("Maya", "Rio", "Sam")
MODULE_NAME = "genie_fleet_native"

NATIVE_SUFFIXES = (".so", ".pyd")


def wheel_members(wheel_path: str) -> list[str]:
    """List member names of the single wheel matching ``wheel_path``."""
    matches = sorted(glob.glob(wheel_path))
    assert len(matches) == 1, f"expected one wheel for {wheel_path!r}, found {matches}"
    with zipfile.ZipFile(matches[0]) as archive:
        return archive.namelist()


def assert_no_native_artifacts(members: list[str]) -> None:
    """Fail when any wheel member is a native binary."""
    binaries = [n for n in members if n.endswith(NATIVE_SUFFIXES)]
    assert not binaries, f"pure-Python wheel must carry no .so/.pyd, found {binaries}"


def find_top_level_native(members: list[str]) -> str:
    """Return the wheel-root ``genie_fleet_native<EXT_SUFFIX>`` member.

    ``_native.py`` probes the top-level import name, so a nested ``.so``
    would ship dead weight: only a root member with the exact module stem
    passes.
    """
    candidates = [
        n
        for n in members
        if n.endswith(NATIVE_SUFFIXES) and Path(n).name.startswith(MODULE_NAME)
    ]
    assert candidates, "native wheel must contain genie_fleet_native"
    assert len(candidates) == 1, f"expected one native member, found {candidates}"
    member = candidates[0]
    assert "/" not in member, f".so must sit at the wheel root, got {member}"
    bare = member[: -len(Path(member).suffix)]
    assert bare == MODULE_NAME or bare.startswith(MODULE_NAME + "."), (
        f"misnamed native member: {member}"
    )
    return member


def check_golden_byte_identical() -> dict[str, object]:
    """Maya sick-leave report must equal the committed golden fixture."""
    from genie_fleet.agent import run_dispatch_request

    outcome = run_dispatch_request("Maya called in sick")
    golden = json.loads(GOLDEN.read_text())
    assert outcome["absent_tech"] == golden["absent_tech"]
    assert outcome["report"] == golden["report"], "golden fixture mismatch"
    report = outcome["report"]
    assert isinstance(report, dict)
    return report


def check_maya_dispatch() -> dict[str, object]:
    """Maya dispatch over HTTP: 2 moved / 6 total with canned fuel."""
    from fastapi.testclient import TestClient

    from genie_fleet.api import create_app

    response = TestClient(create_app()).post("/dispatch", json={"absent_tech": "Maya"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-Id"), "X-Request-Id missing"
    body = response.json()
    assert body["report"]["tasks_moved"] == 2
    assert body["report"]["tasks_total"] == 6
    assert body["report"]["fuel_before"] == 12.7
    assert body["report"]["fuel_after"] == 22.43
    assert isinstance(body, dict)
    return body


def reports_equal(first: dict[str, object], second: dict[str, object]) -> bool:
    """Byte-equality for dispatch reports (key order is construction order)."""
    return json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def native_parity_reports() -> dict[str, dict[str, object] | None]:
    """Per-outage native reports; None means honest Python fallback."""
    from genie_fleet import _native as native_shim

    reports: dict[str, dict[str, object] | None] = {}
    for absent in OUTAGES:
        report = native_shim.try_native_optimize(absent, True)
        reports[absent] = report
    return reports


def check_native_parity() -> None:
    """Every outage's native report must byte-equal ``matrix.optimize``."""
    from genie_fleet.matrix import optimize

    reports = native_parity_reports()
    for absent in OUTAGES:
        native_report = reports[absent]
        assert native_report is not None, f"native report missing for {absent}"
        expected = optimize(absent)
        assert reports_equal(native_report, expected), f"native differs for {absent}"


def check_expect_pure() -> None:
    from genie_fleet import _native as native_shim

    assert native_shim.NATIVE_AVAILABLE is False, "flag-off wheel must stay pure"
    check_golden_byte_identical()
    body = check_maya_dispatch()
    assert body["path"].startswith("direct-tool"), body["path"]
    assert "native" not in body["path"], body["path"]
    print("wheel-smoke: pure-Python install green (golden byte-identical, Maya 2/6)")


def check_expect_native() -> None:
    from genie_fleet import _native as native_shim

    assert native_shim.NATIVE_AVAILABLE is True, "flag-on wheel must ship the .so"
    check_golden_byte_identical()
    body = check_maya_dispatch()
    assert "native" in body["path"], body["path"]
    check_native_parity()
    print("wheel-smoke: native install green (byte-equal reports, replay match)")


def check_wheel(path: str, expect_native: bool) -> None:
    members = wheel_members(path)
    if expect_native:
        member = find_top_level_native(members)
        print(f"wheel-smoke: native wheel carries top-level {member}")
    else:
        assert_no_native_artifacts(members)
        print("wheel-smoke: pure-Python wheel carries no .so/.pyd")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Installed-wheel smoke checks")
    parser.add_argument("--check-wheel", default=None)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--expect-pure", action="store_true")
    group.add_argument("--expect-native", action="store_true")
    args = parser.parse_args(argv)
    if args.check_wheel is not None:
        check_wheel(args.check_wheel, args.expect_native)
    elif args.expect_native:
        check_expect_native()
    else:
        check_expect_pure()
    return 0


if __name__ == "__main__":
    sys.exit(main())
