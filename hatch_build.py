"""Best-effort native wheel hook (M10 packaging, approach B, user-approved).

Hatchling custom build hook for wheel builds only (wired via
``[tool.hatch.build.targets.wheel.hooks.custom]`` in ``pyproject.toml``;
no backend change, no new ``build-system.requires``).

Contract (authoritative: ``library/packaging.md``):

1. Strict no-op unless ``GENIE_NATIVE=1``. The default build never shells
   out and produces the identical pure-Python wheel.
2. With the flag, ``native/`` is configured with cmake+Ninja (mise pins)
   into a temp dir, built, and the resulting
   ``genie_fleet_native<EXT_SUFFIX>`` is force-included at the WHEEL TOP
   LEVEL. It must never nest inside ``src/genie_fleet``: ``_native.py``
   probes the top-level import name, so a nested ``.so`` would ship dead
   weight with ``NATIVE_AVAILABLE`` stuck False.
3. ANY failure (no cmake/Ninja/pybind11, configure/compile failure, any
   surprise) prints a warning and returns normally. The wheel build NEVER
   fails because of native; it degrades to the pure-Python wheel.

Revert by deleting this file plus the ``hooks.custom`` stanza.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

#: Exact on-value for the build flag; anything else is a strict no-op.
FLAG_ENV_VAR = "GENIE_NATIVE"
FLAG_ON = "1"

#: Extension module name probed by ``src/genie_fleet/_native.py``.
MODULE_NAME = "genie_fleet_native"

#: Prefix for the temp build dir (outside the repo root, always cleaned).
BUILD_DIR_PREFIX = "genie-native-wheel."


def _flag_on() -> bool:
    """True only when the build flag requests the native wheel."""
    return os.environ.get(FLAG_ENV_VAR) == FLAG_ON


def _warn(reason: str) -> None:
    """Warn on stderr that the wheel degrades to pure Python (never an error)."""
    print(
        f"warning: genie-native: {reason}; building pure-Python wheel",
        file=sys.stderr,
    )


#: Env vars scrubbed from interpreter probes (build-isolation levers).
IGNORED_PROBE_ENV = ("PYTHONPATH", "PYTHONNOUSERSITE")


def _probe_env() -> dict[str, str]:
    """Env for interpreter probes, scrubbed of build-isolation levers.

    ``pip wheel``-style isolation clobbers ``PYTHONPATH`` to point at
    the build env, whose ``sitecustomize`` swaps the base site-packages
    out of ``sys.path``. A probe inheriting the backend env therefore
    cannot see the outer repo env where pybind11 is pinned; dropping
    those vars restores the interpreter's default package set.
    """
    return {
        key: value for key, value in os.environ.items() if key not in IGNORED_PROBE_ENV
    }


def _probe_pybind11(command: list[str]) -> str | None:
    """Run the pybind11 CMake-dir probe; None unless it yields a real dir."""
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=120, env=_probe_env()
        )
    except OSError, subprocess.SubprocessError:
        return None
    if result.returncode != 0:
        return None
    lines = result.stdout.strip().splitlines()
    if lines and os.path.isdir(lines[-1]):
        return lines[-1]
    return None


def _resolved_python(directory: str, name: str) -> str | None:
    """Resolve ``directory/name`` to a real interpreter path, else None.

    A ``python*`` name may resolve to a non-interpreter shim (e.g. a
    task runner); only keep paths that really look like an interpreter.
    """
    candidate = os.path.join(directory, name)
    if not (os.path.isfile(candidate) and os.access(candidate, os.X_OK)):
        return None
    resolved = os.path.realpath(candidate)
    if not os.path.basename(resolved).startswith("python"):
        return None
    return resolved


def _outer_python_candidates() -> list[str]:
    """``python*`` executables on PATH outside the running interpreter's dir.

    Build isolation runs this hook from a venv whose ``bin`` dir shadows
    every generic ``python`` name, so those names alone can never reach
    the outer repo env where pybind11 is pinned. Skipping the running
    interpreter's own bin dir lets the scan fall through to it.
    """
    try:
        own_bin = os.path.dirname(os.path.realpath(sys.executable))
    except OSError:
        own_bin = ""
    names = (
        "python",
        "python3",
        f"python{sys.version_info.major}.{sys.version_info.minor}",
    )
    candidates: list[str] = []
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        try:
            if os.path.realpath(directory) == own_bin:
                continue
        except OSError:
            continue
        for name in names:
            resolved = _resolved_python(directory, name)
            if resolved is None:
                continue
            if resolved not in candidates:
                candidates.append(resolved)
    return candidates


def _pybind11_cmake_dir() -> str | None:
    """Locate pybind11's CMake config dir, or None when unavailable.

    The isolated build env never has pybind11 (it stays out of
    ``build-system.requires`` on purpose), so probe the running build
    interpreter first and then fall back to the ``python*`` executables
    on PATH outside the isolated venv's bin dir, which is the outer
    repo env where pybind11 is pinned. A version mismatch is still safe:
    ``native/CMakeLists.txt`` requires exactly 3.1.0, so configure
    fails and the build degrades to pure Python with a warning.
    """
    probe = "import pybind11; print(pybind11.get_cmake_dir())"
    commands = [[sys.executable, "-c", probe]]
    commands += [[candidate, "-c", probe] for candidate in _outer_python_candidates()]
    for command in commands:
        found = _probe_pybind11(command)
        if found is not None:
            return found
    return None


def _built_extension(build_dir: str) -> Path | None:
    """Find the built module under its full ``EXT_SUFFIX`` name, else None."""
    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
    exact = Path(build_dir) / f"{MODULE_NAME}{ext_suffix}"
    if exact.is_file():
        return exact
    fallbacks = sorted(Path(build_dir).glob(f"{MODULE_NAME}*.so"))
    fallbacks += sorted(Path(build_dir).glob(f"{MODULE_NAME}*.pyd"))
    return fallbacks[0] if fallbacks else None


def _try_native_build(
    native_dir: str, build_dir: str, pybind11_dir: str
) -> Path | None:
    """Configure+compile ``native/`` into ``build_dir``; None on any failure."""
    try:
        subprocess.run(
            [
                "cmake",
                "-S",
                native_dir,
                "-B",
                build_dir,
                "-G",
                "Ninja",
                "-DCMAKE_BUILD_TYPE=Release",
                f"-Dpybind11_DIR={pybind11_dir}",
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=True,
        )
        subprocess.run(
            ["cmake", "--build", build_dir],
            capture_output=True,
            text=True,
            timeout=600,
            check=True,
        )
    except OSError, subprocess.SubprocessError:
        return None
    return _built_extension(build_dir)


class NativeWheelHook(BuildHookInterface):
    """Best-effort hook: flag-on temp build, always safe to degrade."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._native_temp_dirs: list[str] = []

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if not _flag_on():
            return
        if self.target_name != "wheel":
            return
        if shutil.which("cmake") is None or shutil.which("ninja") is None:
            _warn("cmake and Ninja were not found on PATH")
            return
        pybind11_dir = _pybind11_cmake_dir()
        if pybind11_dir is None:
            _warn("pybind11 is not importable, its CMake config is unavailable")
            return
        native_dir = os.path.join(self.root, "native")
        if not os.path.isdir(native_dir):
            _warn(f"native sources missing at {native_dir}")
            return
        build_dir = tempfile.mkdtemp(prefix=BUILD_DIR_PREFIX)
        self._native_temp_dirs.append(build_dir)
        try:
            built = _try_native_build(native_dir, build_dir, pybind11_dir)
        except Exception:  # never break the wheel build for native
            _warn("native build raised unexpectedly")
            return
        if built is None:
            _warn("native configure or compile failed")
            return
        # Top-level placement: _native.py probes find_spec("genie_fleet_native").
        build_data.setdefault("force_include", {})[str(built)] = built.name

    def finalize(
        self, version: str, build_data: dict[str, Any], artifact_path: str
    ) -> None:
        for temp_dir in self._native_temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)
        self._native_temp_dirs.clear()
