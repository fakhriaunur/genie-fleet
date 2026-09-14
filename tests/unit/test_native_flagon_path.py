"""S3 tracer bullet: opt-in flag-on dispatch over plain lists (no Arrow yet).

``try_native_optimize`` converts tasks to SoA lists and calls the
compiled extension ONLY when ``should_use_native()`` is true, else
returns None for the Python fallback. The singular dispatch path routes
natively under GENIE_NATIVE=1 with the extension present (byte-equal
reports for all outages) and falls back honestly when the extension is
absent. Multi-outage stays Python (explicitly out of scope).
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
from genie_fleet.agent import run_dispatch_request, run_multi_dispatch_request
from genie_fleet.matrix import TECH_HOME, optimize, optimize_many
from genie_fleet.settings import Settings

pybind11 = pytest.importorskip("pybind11")

REPO_ROOT = Path(__file__).resolve().parents[2]

OUTAGES = ["Maya", "Rio", "Sam"]

NEEDS_TOOLCHAIN = pytest.mark.skipif(
    shutil.which("cmake") is None or shutil.which("ninja") is None,
    reason="S3 needs the mise-pinned cmake+ninja toolchain",
)


@pytest.mark.parametrize("absent", OUTAGES)
def test_flag_off_returns_none_for_python_fallback(absent: str) -> None:
    """Flag off: helper returns None so the pure-Python path runs unchanged."""
    assert native_shim.try_native_optimize(absent, False) is None
    assert native_shim.try_native_optimize(absent, use_native_flag=False) is None


@pytest.mark.parametrize("absent", OUTAGES)
def test_flag_on_absent_extension_falls_back_honestly(absent: str) -> None:
    """GENIE_NATIVE=1 but no extension: None + Python reports, replay-safe."""
    assert importlib.util.find_spec("genie_fleet_native") is None
    assert native_shim.try_native_optimize(absent, True) is None
    outcome = run_dispatch_request(
        f"{absent} called in sick",
        settings=Settings(mode="mock", use_native=True),
    )
    assert outcome["report"] == optimize(absent)
    assert str(outcome["path"]).startswith("direct-tool")
    assert "native" not in str(outcome["path"])


def test_flag_off_default_zero_behavior_change() -> None:
    """GENIE_NATIVE unset: singular path equals matrix.optimize exactly."""
    for absent in OUTAGES:
        outcome = run_dispatch_request(f"{absent} called in sick")
        assert outcome["report"] == optimize(absent)
        assert str(outcome["path"]).startswith("direct-tool")


def test_multi_outage_stays_python_under_flag_on() -> None:
    """Multi-outage is out of scope: flag-on still runs Python, same report."""
    outcome = run_multi_dispatch_request(
        ["Maya", "Rio"], settings=Settings(mode="mock", use_native=True)
    )
    assert outcome["report"] == optimize_many(["Maya", "Rio"])
    assert "native" not in str(outcome["path"])


def _run_step(args: list[str], label: str) -> None:
    result = subprocess.run(
        args, capture_output=True, text=True, cwd=REPO_ROOT, timeout=600
    )
    assert result.returncode == 0, (
        f"S3 {label} failed (exit {result.returncode}):\n"
        f"{result.stdout[-3000:]}\n{result.stderr[-3000:]}"
    )


@pytest.fixture
def native_present(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Build the extension to a temp dir and present it as importable.

    Same throwaway pattern as S2 (explicit spec load, ``sys.path``
    untouched) plus monkeypatching the shim's ``NATIVE_AVAILABLE`` probe
    True, simulating a process booted with the extension installed.
    Everything is torn down afterwards: no ``.so`` in the tree.
    """
    build_dir = Path(tempfile.mkdtemp(prefix="genie-native-s3."))
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
        assert so_files, f"S3 build produced no .so in {build_dir}"
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
        monkeypatch.setattr(native_shim, "NATIVE_AVAILABLE", True)
        yield module
    finally:
        sys.modules.pop("genie_fleet_native", None)
        shutil.rmtree(build_dir, ignore_errors=True)


@NEEDS_TOOLCHAIN
def test_flag_on_with_extension_byte_equal_all_outages(native_present: Any) -> None:
    """GENIE_NATIVE=1 + extension: native reports byte-equal Python."""
    assert native_shim.should_use_native(True) is True
    settings = Settings(mode="mock", use_native=True)
    for absent in OUTAGES:
        expected = optimize(absent)
        native_report = native_shim.try_native_optimize(absent, True)
        assert native_report is not None
        assert native_report == expected
        outcome = run_dispatch_request(f"{absent} called in sick", settings=settings)
        assert outcome["report"] == expected
        path = str(outcome["path"])
        assert path.startswith("direct-tool")
        assert "native" in path


@NEEDS_TOOLCHAIN
def test_unknown_tech_never_routes_natively(native_present: Any) -> None:
    """Unknown tech: helper returns None so the Python error path owns it."""
    assert native_shim.try_native_optimize("Zed", True) is None
    assert set(TECH_HOME) == {"Maya", "Rio", "Sam"}
