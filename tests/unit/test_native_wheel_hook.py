"""M10 packaging: best-effort native wheel hook (approach B, user-approved).

Covers the ``hatch_build.py`` contract from ``library/packaging.md``:

- default build (``GENIE_NATIVE`` unset) is a strict no-op: never shells
  out, never touches ``build_data``, and the wheel carries no ``.so``;
- flag-on (``GENIE_NATIVE=1``) temp-builds ``native/`` and force-includes
  ``genie_fleet_native<EXT_SUFFIX>`` at the wheel TOP LEVEL (never nested
  inside ``src/genie_fleet``, which ``_native.py`` does not probe);
- ANY toolchain failure warns and returns normally, so the wheel still
  builds pure-Python (exit 0, no error);
- sdist force-includes the ``native/`` C++ sources and no binaries.

Hook-level tests run hermetically (``hatch_build.py`` loads straight from
the repo root with the hatchling base stubbed, so no build backend is
installed); the ``e2e`` tests drive a real ``python -m build`` in a
throwaway venv and skip when PyPI is unreachable.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import sysconfig
import tarfile
import tomllib
import types
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HATCH_BUILD = REPO_ROOT / "hatch_build.py"

#: Native C++ sources the sdist must ship (VAL-PACK-004).
NATIVE_SOURCES = (
    "native/fleet_core.cpp",
    "native/fleet_core.hpp",
    "native/CMakeLists.txt",
)

#: Exact on-value for the build flag: anything else is a strict no-op.
FLAG_ON = "1"


def _install_hatchling_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> type:
    """Stub the hatchling hook base so ``hatch_build.py`` loads hermetically.

    The repo env deliberately has no hatchling installed (it lives only in
    ``build-system.requires`` for build isolation); the stub exposes just
    the ``root``/``target_name`` surface the hook under test uses.
    """

    class BuildHookInterface:
        PLUGIN_NAME = ""

        def __init__(
            self, root: str = "", config: object = None, **kwargs: object
        ) -> None:
            self._hook_root = root
            self._hook_target = str(kwargs.get("target_name", "wheel"))

        @property
        def root(self) -> str:
            return self._hook_root

        @property
        def target_name(self) -> str:
            return self._hook_target

    for name in (
        "hatchling",
        "hatchling.builders",
        "hatchling.builders.hooks",
        "hatchling.builders.hooks.plugin",
        "hatchling.builders.hooks.plugin.interface",
    ):
        module = types.ModuleType(name)
        monkeypatch.setitem(sys.modules, name, module)
    interface = sys.modules["hatchling.builders.hooks.plugin.interface"]
    interface.BuildHookInterface = BuildHookInterface  # type: ignore[attr-defined]
    return BuildHookInterface


def _load_hook(monkeypatch: pytest.MonkeyPatch) -> tuple[types.ModuleType, type]:
    """Exec ``hatch_build.py`` and return ``(module, hook_class)``."""
    base = _install_hatchling_stub(monkeypatch)
    assert HATCH_BUILD.is_file(), "hatch_build.py missing at repo root"
    spec = importlib.util.spec_from_file_location("hatch_build", HATCH_BUILD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hooks = [
        obj
        for name in dir(module)
        if not name.startswith("_")
        for obj in (getattr(module, name),)
        if isinstance(obj, type) and issubclass(obj, base) and obj is not base
    ]
    assert len(hooks) == 1, f"expected one BuildHookInterface subclass, found {hooks}"
    return module, hooks[0]


def _new_hook(hook_cls: type) -> object:
    return hook_cls(str(REPO_ROOT), {}, target_name="wheel")  # type: ignore[call-arg]


def _fresh_build_data() -> dict:
    return {"force_include": {}, "artifacts": []}


def _needs_toolchain() -> pytest.MarkDecorator:
    return pytest.mark.skipif(
        shutil.which("cmake") is None
        or shutil.which("ninja") is None
        or importlib.util.find_spec("pybind11") is None,
        reason="flag-on build needs the mise cmake+ninja toolchain and pybind11",
    )


def test_hook_module_defines_single_build_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    _, hook_cls = _load_hook(monkeypatch)
    assert hook_cls.PLUGIN_NAME in ("", "custom")


@pytest.mark.parametrize("flag", [None, "0", "", "true"])
def test_default_build_is_strict_noop(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, flag: str | None
) -> None:
    """Without ``GENIE_NATIVE=1`` the hook never shells out or mutates data."""
    _, hook_cls = _load_hook(monkeypatch)
    if flag is None:
        monkeypatch.delenv("GENIE_NATIVE", raising=False)
    else:
        monkeypatch.setenv("GENIE_NATIVE", flag)

    def _no_shell(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"default build must not shell out: {args!r}")

    monkeypatch.setattr(subprocess, "run", _no_shell)
    build_data = _fresh_build_data()
    hook = _new_hook(hook_cls)
    assert hook.initialize("standard", build_data) is None  # type: ignore[attr-defined]
    assert build_data == _fresh_build_data()
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


@_needs_toolchain()
def test_flag_on_places_so_at_wheel_top_level(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Flag-on temp build force-includes the ``.so`` at the wheel root."""
    _, hook_cls = _load_hook(monkeypatch)
    monkeypatch.setenv("GENIE_NATIVE", FLAG_ON)
    build_data = _fresh_build_data()
    hook = _new_hook(hook_cls)
    assert hook.initialize("standard", build_data) is None  # type: ignore[attr-defined]
    forced = build_data["force_include"]
    assert len(forced) == 1
    source, target = next(iter(forced.items()))
    assert Path(source).is_file(), f"force-included source missing: {source}"
    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
    assert target == f"genie_fleet_native{ext_suffix}"
    assert "/" not in target, f".so must sit at the wheel root, got {target}"
    assert not target.startswith("genie_fleet/"), f".so nested in package: {target}"
    hook.finalize("standard", build_data, "artifact.whl")  # type: ignore[attr-defined]
    assert not Path(source).exists(), "hook temp dir must be cleaned in finalize"
    assert list(Path("/tmp").glob("genie-native-wheel.*")) == []


def test_flag_on_without_toolchain_warns_and_returns_pure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
) -> None:
    """``GENIE_NATIVE=1`` with no cmake degrades to a pure wheel quietly."""
    _, hook_cls = _load_hook(monkeypatch)
    monkeypatch.setenv("GENIE_NATIVE", FLAG_ON)
    monkeypatch.setenv("PATH", str(tmp_path))
    build_data = _fresh_build_data()
    hook = _new_hook(hook_cls)
    assert hook.initialize("standard", build_data) is None  # type: ignore[attr-defined]
    assert build_data == _fresh_build_data()
    err = capsys.readouterr().err.lower()
    assert "warning" in err
    assert "traceback" not in err
    assert "error" not in err


def test_flag_on_build_failure_warns_and_returns_pure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """``GENIE_NATIVE=1`` with a broken toolchain still returns normally."""
    _, hook_cls = _load_hook(monkeypatch)
    monkeypatch.setenv("GENIE_NATIVE", FLAG_ON)

    def _broken(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("simulated broken compiler")

    monkeypatch.setattr(subprocess, "run", _broken)
    build_data = _fresh_build_data()
    hook = _new_hook(hook_cls)
    assert hook.initialize("standard", build_data) is None  # type: ignore[attr-defined]
    assert build_data == _fresh_build_data()
    err = capsys.readouterr().err.lower()
    assert "warning" in err
    assert "traceback" not in err


def test_pybind11_probe_survives_build_isolation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The pybind11 lookup works under ``pip wheel``-style isolation.

    Build isolation clobbers ``PYTHONPATH`` to the build env, whose
    ``sitecustomize`` swaps the base site-packages out of ``sys.path``;
    the probe must scrub those levers so it still sees the outer repo
    env where pybind11 is pinned (regression: bare ``pip wheel`` with
    ``GENIE_NATIVE=1`` degraded although the toolchain was present).
    """
    module, _ = _load_hook(monkeypatch)
    poison = tmp_path / "poison"
    poison.mkdir()
    (poison / "sitecustomize.py").write_text(
        "import sys\nsys.path[:] = [p for p in sys.path if 'site-packages' not in p]\n"
    )
    monkeypatch.setenv("PYTHONPATH", str(poison))
    monkeypatch.setenv("PYTHONNOUSERSITE", "1")
    found = module._pybind11_cmake_dir()
    assert found is not None, "probe lost pybind11 under simulated isolation"
    assert os.path.isdir(found)
    scrubbed = module._probe_env()
    assert "PYTHONPATH" not in scrubbed
    assert "PYTHONNOUSERSITE" not in scrubbed


def test_outer_candidates_keep_real_interpreters_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """PATH ``python*`` names resolving to non-interpreters are skipped."""
    module, _ = _load_hook(monkeypatch)
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    decoy = fake_bin / "python"
    decoy.symlink_to(os.path.realpath("/bin/sh"))
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}")
    for candidate in module._outer_python_candidates():
        assert os.path.basename(candidate).startswith("python"), candidate


def test_pyproject_wires_wheel_hook_and_sdist_sources() -> None:
    """``pyproject.toml`` wires the hook with no backend/dependency change."""
    with open(REPO_ROOT / "pyproject.toml", "rb") as handle:
        config = tomllib.load(handle)
    assert config["build-system"]["requires"] == ["hatchling"]
    assert config["build-system"]["build-backend"] == "hatchling.build"
    wheel_hooks = config["tool"]["hatch"]["build"]["targets"]["wheel"]["hooks"]
    assert "custom" in wheel_hooks
    sdist_include = config["tool"]["hatch"]["build"]["targets"]["sdist"][
        "force-include"
    ]
    for source in NATIVE_SOURCES:
        assert source in sdist_include, f"sdist missing native source: {source}"
        assert sdist_include[source] == source


def _pypi_reachable() -> bool:
    try:
        socket.create_connection(("pypi.org", 443), timeout=5).close()
    except OSError:
        return False
    return True


_PYPI_OK = _pypi_reachable()

needs_pypi = pytest.mark.skipif(not _PYPI_OK, reason="wheel e2e needs PyPI")


@pytest.fixture(scope="module")
def build_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Throwaway venv with ``build`` installed for real PEP 517 builds."""
    venv = tmp_path_factory.mktemp("wheel-e2e-venv")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        subprocess.run(
            [str(venv / "bin" / "pip"), "install", "build"],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        pytest.skip(f"wheel e2e venv unavailable: {exc}")
    return venv / "bin" / "python"


@pytest.fixture()
def staged_repo(tmp_path: Path) -> Path:
    """Copy the build inputs to a temp dir so e2e never pollutes the tree."""
    dest = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT,
        dest,
        ignore=shutil.ignore_patterns(
            ".git",
            "__pycache__",
            ".venv",
            "dist",
            "build",
            "*.egg-info",
            ".pytest_cache",
            ".coverage",
        ),
    )
    return dest


def _real_tool_dirs() -> list[str]:
    """Bin dirs of the mise-pinned cmake+ninja, resolved from the repo root.

    The staged copy carries its own (untrusted) ``mise.toml``, so the
    cmake/ninja shims would refuse there. A normal checkout is trusted
    via ``mise trust`` and the shims resolve to these same binaries, so
    prepending the real dirs keeps e2e on the identical toolchain.
    """
    dirs: list[str] = []
    for tool in ("cmake", "ninja"):
        try:
            result = subprocess.run(
                ["mise", "which", tool],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=REPO_ROOT,
            )
        except OSError:
            continue
        if result.returncode != 0:
            continue
        lines = result.stdout.strip().splitlines()
        if lines:
            dirs.append(os.path.dirname(lines[-1]))
    return dirs


def _run_pep517(
    build_python: Path,
    staged: Path,
    target: str,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("GENIE_NATIVE", None)
    real_dirs = _real_tool_dirs()
    if real_dirs:
        env["PATH"] = os.pathsep.join([*real_dirs, env.get("PATH", "")])
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [str(build_python), "-m", "build", f"--{target}", "--outdir", "dist", "."],
        capture_output=True,
        text=True,
        timeout=900,
        cwd=staged,
        env=env,
    )


def _wheel_members(staged: Path) -> list[str]:
    wheels = sorted((staged / "dist").glob("*.whl"))
    assert len(wheels) == 1, f"expected one wheel, found {wheels}"
    with zipfile.ZipFile(wheels[0]) as archive:
        return archive.namelist()


@needs_pypi
def test_e2e_default_wheel_has_no_so(build_python: Path, staged_repo: Path) -> None:
    result = _run_pep517(build_python, staged_repo, "wheel")
    assert result.returncode == 0, result.stderr[-2000:]
    assert not [n for n in _wheel_members(staged_repo) if n.endswith((".so", ".pyd"))]


@needs_pypi
@_needs_toolchain()
def test_e2e_flag_on_places_so_at_top_level(
    build_python: Path, staged_repo: Path
) -> None:
    result = _run_pep517(build_python, staged_repo, "wheel", {"GENIE_NATIVE": FLAG_ON})
    assert result.returncode == 0, result.stderr[-2000:]
    native = [n for n in _wheel_members(staged_repo) if "genie_fleet_native" in n]
    assert len(native) == 1
    assert "/" not in native[0], f".so nested in wheel: {native[0]}"


@needs_pypi
def test_e2e_flag_on_broken_toolchain_still_exits_0(
    build_python: Path, staged_repo: Path, tmp_path: Path
) -> None:
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    fake_cmake = fake_bin / "cmake"
    fake_cmake.write_text("#!/bin/sh\nexit 1\n")
    fake_cmake.chmod(0o755)
    env_extra = {
        "GENIE_NATIVE": FLAG_ON,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    result = _run_pep517(build_python, staged_repo, "wheel", env_extra)
    combined = (result.stdout + result.stderr).lower()
    assert result.returncode == 0, result.stderr[-2000:]
    assert "warning" in combined
    assert "traceback" not in combined
    assert not [n for n in _wheel_members(staged_repo) if n.endswith((".so", ".pyd"))]


@needs_pypi
def test_e2e_sdist_ships_native_sources_no_binaries(
    build_python: Path, staged_repo: Path
) -> None:
    result = _run_pep517(build_python, staged_repo, "sdist")
    assert result.returncode == 0, result.stderr[-2000:]
    sdists = sorted((staged_repo / "dist").glob("*.tar.gz"))
    assert len(sdists) == 1, f"expected one sdist, found {sdists}"
    with tarfile.open(sdists[0]) as archive:
        names = archive.getnames()
    tops = {name.split("/")[0] for name in names}
    assert len(tops) == 1, f"sdist has no single top dir: {sorted(tops)}"
    prefix = f"{next(iter(tops))}/"
    for source in NATIVE_SOURCES:
        assert f"{prefix}{source}" in names, f"sdist missing {source}"
    assert not [n for n in names if n.endswith((".so", ".pyd"))]
