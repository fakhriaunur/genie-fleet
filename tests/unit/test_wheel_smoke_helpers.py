"""M10 verify: unit tests for the installed-wheel smoke helper.

``scripts/wheel_smoke.py`` is the shared assertion core used both by
``mise run verify-wheel`` and the CI wheel jobs. Its pure helpers
(wheel-member listing, native-artifact asserts) run hermetically; the
behavioral checks run against the repo checkout here (pure-Python,
``NATIVE_AVAILABLE`` False) and against installed wheels in CI/verify.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from genie_fleet import _native as native_shim

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "wheel_smoke.py"
GOLDEN = REPO_ROOT / "tests" / "replay" / "fixtures" / "dispatch_golden.json"

PURE_MEMBERS = [
    "genie_fleet/__init__.py",
    "genie_fleet/api.py",
    "genie_fleet-0.1.0.dist-info/METADATA",
]

EXT_SUFFIX = "genie_fleet_native.cpython-314-x86_64-linux-gnu.so"


def _load_smoke() -> object:
    import importlib.util

    assert SMOKE_SCRIPT.is_file(), "scripts/wheel_smoke.py missing"
    spec = importlib.util.spec_from_file_location("wheel_smoke", SMOKE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_assert_no_native_artifacts_passes_on_pure_members() -> None:
    smoke = _load_smoke()
    assert smoke.assert_no_native_artifacts(PURE_MEMBERS) is None


@pytest.mark.parametrize("artifact", [EXT_SUFFIX, "genie_fleet_native.pyd"])
def test_assert_no_native_artifacts_fails_on_binaries(artifact: str) -> None:
    smoke = _load_smoke()
    with pytest.raises(AssertionError):
        smoke.assert_no_native_artifacts([*PURE_MEMBERS, artifact])


def test_find_top_level_native_accepts_wheel_root_so() -> None:
    smoke = _load_smoke()
    assert smoke.find_top_level_native([*PURE_MEMBERS, EXT_SUFFIX]) == EXT_SUFFIX


def test_find_top_level_native_rejects_nested_so() -> None:
    smoke = _load_smoke()
    with pytest.raises(AssertionError):
        smoke.find_top_level_native([*PURE_MEMBERS, f"genie_fleet/{EXT_SUFFIX}"])


def test_find_top_level_native_rejects_missing_so() -> None:
    smoke = _load_smoke()
    with pytest.raises(AssertionError):
        smoke.find_top_level_native(PURE_MEMBERS)


def test_find_top_level_native_rejects_misnamed_so() -> None:
    smoke = _load_smoke()
    with pytest.raises(AssertionError):
        smoke.find_top_level_native([*PURE_MEMBERS, "native.so"])


def test_wheel_members_lists_archive_names(tmp_path: Path) -> None:
    smoke = _load_smoke()
    wheel = tmp_path / "probe-0.1-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in PURE_MEMBERS:
            archive.writestr(name, "")
    assert smoke.wheel_members(str(wheel)) == PURE_MEMBERS


def test_golden_byte_identical_in_repo_env() -> None:
    """Repo checkout (pure Python) matches the committed golden fixture."""
    smoke = _load_smoke()
    report = smoke.check_golden_byte_identical()
    golden = json.loads(GOLDEN.read_text())
    assert report == golden["report"]


def test_maya_dispatch_shape_in_repo_env() -> None:
    """Maya dispatch smoke: 2 moved / 6 total with canned fuel numbers."""
    smoke = _load_smoke()
    body = smoke.check_maya_dispatch()
    assert body["report"]["tasks_moved"] == 2
    assert body["report"]["tasks_total"] == 6
    assert body["report"]["fuel_before"] == 12.7
    assert body["report"]["fuel_after"] == 22.43


def test_native_parity_reports_none_without_extension() -> None:
    """Without the compiled extension the parity probe stays honest: None.

    The repo env never installs the extension (repo-fit contract), so the
    native reports are None here and ``--expect-native`` must refuse them.
    """
    assert native_shim.NATIVE_AVAILABLE is False
    smoke = _load_smoke()
    assert smoke.native_parity_reports() == {"Maya": None, "Rio": None, "Sam": None}
    with pytest.raises(AssertionError):
        smoke.check_native_parity()


def test_reports_equal_spots_mismatch() -> None:
    smoke = _load_smoke()
    report = {"tasks_moved": 2, "fuel_before": 12.7}
    assert smoke.reports_equal(report, dict(report)) is True
    assert smoke.reports_equal(report, {**report, "tasks_moved": 3}) is False
