"""S2 tracer bullet: temp-built extension matches Python on all outages.

Builds ``genie_fleet_native`` into a throwaway temp dir (the same
configure+build path as the S1 ``build-native-check`` task, never
installed), loads the ``.so`` via an explicit importlib spec inside the
test (``sys.path`` untouched, the temporary ``sys.modules`` entry removed
on teardown), and asserts
``reassign``/``fuel`` outputs identical to ``matrix.optimize()`` for the
Maya, Rio, and Sam golden numbers. The default flag-off path is
untouched: ``NATIVE_AVAILABLE`` stays False in the repo env. The temp
build dir is deleted afterwards; no ``.so`` lands anywhere in the tree.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from genie_fleet import _native as native_shim
from genie_fleet.matrix import (
    fleet_fuel,
    optimize,
    reassign_sick_leave,
    seed_fleet,
)

pybind11 = pytest.importorskip("pybind11")

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Tech index order. Must match HOME_X/HOME_Y in native/fleet_core.cpp
#: (Maya=0, Rio=1, Sam=2) and the sorted-name tie-break of matrix.py.
TECH_INDEX = ("Maya", "Rio", "Sam")

#: Golden numbers from tests/scenarios/test_happy_dispatch.py.
EXPECTED: dict[str, dict[str, Any]] = {
    "Maya": {
        "tasks_moved": 2,
        "tasks_total": 6,
        "fuel_before": 12.7,
        "fuel_after": 22.43,
        "added_fuel": 9.73,
    },
    "Rio": {
        "tasks_moved": 2,
        "tasks_total": 6,
        "fuel_before": 12.7,
        "fuel_after": 29.28,
        "added_fuel": 16.59,
    },
    "Sam": {
        "tasks_moved": 2,
        "tasks_total": 6,
        "fuel_before": 12.7,
        "fuel_after": 29.28,
        "added_fuel": 16.59,
    },
}

pytestmark = pytest.mark.skipif(
    shutil.which("cmake") is None or shutil.which("ninja") is None,
    reason="S2 needs the mise-pinned cmake+ninja toolchain",
)


def _run_step(args: list[str], label: str) -> None:
    result = subprocess.run(
        args, capture_output=True, text=True, cwd=REPO_ROOT, timeout=600
    )
    assert result.returncode == 0, (
        f"S2 {label} failed (exit {result.returncode}):\n"
        f"{result.stdout[-3000:]}\n{result.stderr[-3000:]}"
    )


@pytest.fixture
def native_mod() -> Any:
    """Build the extension to a temp dir and load it via explicit spec.

    Function-scoped so every load is torn down before the next test:
    the module is exec'd under its true name (the ``.so`` only exports
    ``PyInit_genie_fleet_native``) but ``sys.path`` is never touched and
    the ``sys.modules`` entry is removed on teardown, so the repo env
    keeps ``NATIVE_AVAILABLE`` False outside this fixture.
    """
    build_dir = Path(tempfile.mkdtemp(prefix="genie-native-s2."))
    try:
        _run_step(
            [
                "cmake",
                "-S",
                str(REPO_ROOT / "native"),
                "-B",
                str(build_dir),
                "-G",
                "Ninja",
                "-DCMAKE_BUILD_TYPE=Release",
                f"-Dpybind11_DIR={pybind11.get_cmake_dir()}",
            ],
            "cmake configure",
        )
        _run_step(["cmake", "--build", str(build_dir)], "cmake build")
        so_files = sorted(build_dir.glob("genie_fleet_native*.so"))
        assert so_files, f"S2 build produced no .so in {build_dir}"
        spec = importlib.util.spec_from_file_location("genie_fleet_native", so_files[0])
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["genie_fleet_native"] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop("genie_fleet_native", None)
            raise
        assert isinstance(module, ModuleType)
        yield module
    finally:
        sys.modules.pop("genie_fleet_native", None)
        shutil.rmtree(build_dir, ignore_errors=True)


@pytest.mark.parametrize("absent", ["Maya", "Rio", "Sam"])
def test_native_matches_python_for_outage(native_mod: Any, absent: str) -> None:
    before = seed_fleet()
    xs = [row.x for row in before.rows]
    ys = [row.y for row in before.rows]
    owners = [TECH_INDEX.index(row.assigned_tech) for row in before.rows]
    absent_idx = TECH_INDEX.index(absent)

    # Python report pins the golden numbers for this outage.
    report = optimize(absent)
    for key, value in EXPECTED[absent].items():
        assert report[key] == value, f"{absent}: {key} {report[key]} != {value}"

    # Native reassign matches Python owner-for-owner (exact ints).
    native_owners = list(native_mod.reassign_sick_leave_soa(xs, ys, owners, absent_idx))
    after = reassign_sick_leave(before, absent)
    expected_owners = [TECH_INDEX.index(row.assigned_tech) for row in after.rows]
    assert native_owners == expected_owners

    # Native fuel matches Python to fp noise; rounded values are exact.
    assert native_mod.fleet_fuel_soa(xs, ys, owners) == pytest.approx(
        fleet_fuel(before), abs=1e-9
    )
    assert native_mod.fleet_fuel_soa(xs, ys, native_owners) == pytest.approx(
        fleet_fuel(after), abs=1e-9
    )
    assert (
        round(float(native_mod.fleet_fuel_soa(xs, ys, owners)), 2)
        == (report["fuel_before"])
    )
    assert (
        round(float(native_mod.fleet_fuel_soa(xs, ys, native_owners)), 2)
        == (report["fuel_after"])
    )

    # Native moved count matches the Python report.
    assert owners.count(absent_idx) == report["tasks_moved"]


def test_default_flag_off_path_untouched() -> None:
    assert native_shim.NATIVE_AVAILABLE is False
    assert native_shim.should_use_native(False) is False
    assert importlib.util.find_spec("genie_fleet_native") is None


def test_no_native_artifact_installed_in_tree() -> None:
    assert list(REPO_ROOT.rglob("genie_fleet_native*.so")) == []
    assert list(REPO_ROOT.rglob("genie_fleet_native*.pyd")) == []
