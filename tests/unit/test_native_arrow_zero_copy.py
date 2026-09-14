"""S4 tracer bullet: Arrow zero-copy boundary, still flagged off.

Python builds the task columns as pyarrow arrays, the extension reads the
shared data buffers in place (no per-row Python objects cross the
boundary — proven in-test by comparing the C++-observed data pointer
against the Arrow buffer address), reassignment indices come back in a
caller-owned buffer viewed in place, and ``matrix.dispatch_report``
shapes the unchanged JSON. Default stays flagged off; replay stays
green; pyarrow lives in an isolated prefix only (never ``pyproject``
deps, never the repo env).
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from genie_fleet import _native as native_shim
from genie_fleet.matrix import optimize
from genie_fleet.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]

OUTAGES = ["Maya", "Rio", "Sam"]

#: Tech index order. Must match HOME_X/HOME_Y in native/fleet_core.cpp
#: (Maya=0, Rio=1, Sam=2) and the sorted-name tie-break of matrix.py.
TECH_INDEX = ("Maya", "Rio", "Sam")

#: Canned seed coordinates and owners, mirroring matrix.seed_fleet().
SEED_XS = (2.0, 1.0, 9.0, 11.0, 1.0, 2.0)
SEED_YS = (1.0, 3.0, 1.0, 2.0, 9.0, 11.0)
SEED_OWNERS = (0, 0, 1, 1, 2, 2)

NEEDS_TOOLCHAIN = pytest.mark.skipif(
    shutil.which("cmake") is None or shutil.which("ninja") is None,
    reason="S4 needs the mise-pinned cmake+ninja toolchain",
)

pa: Any = pytest.importorskip("pyarrow")
pybind11: Any = pytest.importorskip("pybind11")


def _arrow_columns() -> dict[str, Any]:
    """Build the seed task columns as pyarrow arrays plus typed views.

    Only buffer-backed views (plus one int each call) may cross into
    C++; no per-row list, tuple, or TaskRow ever crosses the boundary.
    """
    xs_arr = pa.array(SEED_XS, type=pa.float64())
    ys_arr = pa.array(SEED_YS, type=pa.float64())
    owners_arr = pa.array(SEED_OWNERS, type=pa.int64())
    xs_buf = xs_arr.buffers()[1]
    ys_buf = ys_arr.buffers()[1]
    owners_buf = owners_arr.buffers()[1]
    assert xs_buf is not None and ys_buf is not None and owners_buf is not None
    out_buf = pa.allocate_buffer(8 * len(SEED_XS))
    columns = {
        "arrays": (xs_arr, ys_arr, owners_arr),
        "buffers": (xs_buf, ys_buf, owners_buf, out_buf),
        "xs": memoryview(xs_buf).cast("d"),
        "ys": memoryview(ys_buf).cast("d"),
        "owners": memoryview(owners_buf).cast("q"),
        "out": memoryview(out_buf).cast("q"),
    }
    return columns


def _run_step(args: list[str], label: str) -> None:
    result = subprocess.run(
        args, capture_output=True, text=True, cwd=REPO_ROOT, timeout=600
    )
    assert result.returncode == 0, (
        f"S4 {label} failed (exit {result.returncode}):\n"
        f"{result.stdout[-3000:]}\n{result.stderr[-3000:]}"
    )


@pytest.fixture
def native_mod() -> Any:
    """Build the extension to a temp dir and load it via explicit spec.

    Same throwaway pattern as S2/S3: explicit spec load under the true
    module name, ``sys.path`` untouched, ``sys.modules`` entry removed
    on teardown, temp build dir deleted. No ``.so`` lands in the tree.
    """
    build_dir = Path(tempfile.mkdtemp(prefix="genie-native-s4."))
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
        assert so_files, f"S4 build produced no .so in {build_dir}"
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


@pytest.fixture
def native_present(monkeypatch: pytest.MonkeyPatch, native_mod: Any) -> Any:
    """Present the throwaway extension as importable, flag-on simulated.

    Same as S3: monkeypatches the shim's ``NATIVE_AVAILABLE`` probe True
    to simulate a process booted with the extension installed. Torn down
    afterwards; the repo env keeps ``NATIVE_AVAILABLE`` False.
    """
    monkeypatch.setattr(native_shim, "NATIVE_AVAILABLE", True)
    return native_mod


def test_pyarrow_stays_out_of_project_deps() -> None:
    """pyarrow is isolated-only: never a project dependency."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    assert "pyarrow" not in pyproject


def test_pyarrow_absent_from_repo_env() -> None:
    """The repo env itself cannot import pyarrow (isolated prefix only)."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME"}
    }
    result = subprocess.run(
        [sys.executable, "-c", "import pyarrow"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=120,
    )
    assert result.returncode != 0, "pyarrow leaked into the repo env"


@NEEDS_TOOLCHAIN
@pytest.mark.parametrize("absent", OUTAGES)
def test_cpp_reads_shared_arrow_buffers(native_mod: Any, absent: str) -> None:
    """Zero-copy evidence: C++ observes the Arrow buffers' own addresses.

    The data pointer seen through the boundary equals the Arrow data
    buffer address, so the columns are read in place — no per-row
    objects cross. Exactly the buffer views plus one int cross.
    """
    columns = _arrow_columns()
    xs_buf, ys_buf, owners_buf, _ = columns["buffers"]
    for view, buf, name in (
        (columns["xs"], xs_buf, "xs"),
        (columns["ys"], ys_buf, "ys"),
        (columns["owners"], owners_buf, "owners"),
    ):
        assert not isinstance(view, (list, tuple)), f"{name} crossed as rows"
        memoryview(view)  # must expose the buffer protocol
        assert native_mod.buffer_data_ptr(view) == buf.address, (
            f"C++ does not share the Arrow {name} buffer"
        )
    absent_idx = TECH_INDEX.index(absent)
    before_addr = native_mod.buffer_data_ptr(columns["out"])
    native_mod.reassign_sick_leave_buffers(
        columns["xs"], columns["ys"], columns["owners"], absent_idx, columns["out"]
    )
    # Indices come back as a view: the same caller-owned buffer holds them.
    assert native_mod.buffer_data_ptr(columns["out"]) == before_addr
    result = list(columns["out"])
    assert len(result) == len(SEED_XS)
    assert all(isinstance(v, int) for v in result)
    assert all(v != absent_idx for v in result)


@NEEDS_TOOLCHAIN
@pytest.mark.parametrize("absent", OUTAGES)
def test_arrow_path_identical_for_all_outages(native_present: Any, absent: str) -> None:
    """Arrow path returns identical fuel_before/fuel_after/tasks_moved."""
    assert native_shim.should_use_native(True) is True
    report = native_shim.try_native_arrow_optimize(absent, True)
    assert report is not None
    expected = optimize(absent)
    assert report == expected
    for key in ("fuel_before", "fuel_after", "tasks_moved"):
        assert report[key] == expected[key], f"{absent}: {key} differs"
    assert json.dumps(report, sort_keys=True) == json.dumps(expected, sort_keys=True)


@pytest.mark.parametrize("absent", OUTAGES)
def test_flag_off_returns_none_for_python_fallback(absent: str) -> None:
    """Flag off: Arrow helper returns None; the Python path runs unchanged."""
    assert native_shim.try_native_arrow_optimize(absent, False) is None
    assert native_shim.try_native_arrow_optimize(absent, use_native_flag=False) is None


def test_flag_off_default_zero_behavior_change() -> None:
    """GENIE_NATIVE unset: shim gate stays off and extension stays absent."""
    assert Settings().use_native is False
    assert native_shim.should_use_native(False) is False
    assert importlib.util.find_spec("genie_fleet_native") is None


def test_no_pyarrow_returns_none_honestly(
    monkeypatch: pytest.MonkeyPatch, native_present: Any
) -> None:
    """pyarrow uninstallable in-process: None so Python owns the report."""
    monkeypatch.setitem(sys.modules, "pyarrow", None)
    for absent in OUTAGES:
        assert native_shim.try_native_arrow_optimize(absent, True) is None


def test_unknown_tech_never_routes_natively_arrow(native_present: Any) -> None:
    """Unknown tech: helper returns None so the Python error path owns it."""
    assert native_shim.try_native_arrow_optimize("Zed", True) is None


def test_no_native_artifact_installed_in_tree() -> None:
    assert list(REPO_ROOT.rglob("genie_fleet_native*.so")) == []
    assert list(REPO_ROOT.rglob("genie_fleet_native*.pyd")) == []
