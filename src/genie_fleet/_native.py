"""Native dispatch shim (M2 seam probe, flagged off by default).

Tries to locate the compiled ``genie_fleet_native`` extension (pybind11).
When absent — the normal path in this repo — ``NATIVE_AVAILABLE`` is False
and every caller falls back to the pure-Python matrix core. Absence is
expected, never an error: the Python path stays byte-identical either way.

S3 adds :func:`try_native_optimize`: converts the seeded tasks to SoA
lists, calls the extension ONLY when :func:`should_use_native` is true,
and returns None for the Python fallback otherwise. The report shape is
still built by ``matrix.dispatch_report``, so a native success is
byte-equal to ``matrix.optimize()`` by construction (plus a native fuel
cross-check); multi-outage stays Python (explicitly out of scope).

S4 adds :func:`try_native_arrow_optimize`: builds the same seed tasks as
pyarrow columns (in an isolated prefix only — pyarrow is never a project
dependency and never imported at module top), the extension reads the
shared data buffers in place (no per-row objects cross the boundary),
and indices come back in a caller-owned buffer viewed in place. The
report is still shaped by ``matrix.dispatch_report`` (byte-equal), and
the path stays flagged off by default.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
from types import ModuleType
from typing import Any

#: Tech index order. Must match HOME_X/HOME_Y in native/fleet_core.cpp
#: (Maya=0, Rio=1, Sam=2) and the sorted-name tie-break of matrix.py.
TECH_INDEX: tuple[str, str, str] = ("Maya", "Rio", "Sam")

#: True only when the compiled extension is importable in this process.
NATIVE_AVAILABLE: bool = importlib.util.find_spec("genie_fleet_native") is not None

_warned_fallback = False

_logger = logging.getLogger("genie_fleet.native")


def should_use_native(use_native_flag: bool) -> bool:
    """Fail-safe gate for the flagged-off native path.

    Returns True only when the caller requested native AND the extension
    is present. When requested but absent, logs one warning and returns
    False so callers fall back to Python. Never raises.
    """
    global _warned_fallback
    if not use_native_flag:
        return False
    if NATIVE_AVAILABLE:
        return True
    if not _warned_fallback:
        _logger.warning(
            "GENIE_NATIVE=1 but genie_fleet_native is absent; "
            "falling back to pure-Python matrix core"
        )
        _warned_fallback = True
    return False


def _load_extension() -> ModuleType | None:
    """Import the compiled extension, or None when absent. Never raises."""
    try:
        return importlib.import_module("genie_fleet_native")
    except ImportError:
        return None


def _native_reassign(
    ext: ModuleType, xs: list[float], ys: list[float], owners: list[int], absent: int
) -> tuple[list[int], float, float] | None:
    """Call the extension over plain SoA lists.

    Returns ``(owners, fuel_before, fuel_after)`` with fuels rounded to
    2dp, or None on any absence/mismatch/failure so the caller falls
    back to Python honestly.
    """
    reassign = getattr(ext, "reassign_sick_leave_soa", None)
    fuel = getattr(ext, "fleet_fuel_soa", None)
    if not callable(reassign) or not callable(fuel):
        return None
    try:
        result = [int(v) for v in reassign(xs, ys, owners, absent)]
        fuel_before = round(float(fuel(xs, ys, owners)), 2)
        fuel_after = round(float(fuel(xs, ys, result)), 2)
    except Exception:  # pragma: no cover - parity suite proves the happy path
        _logger.warning("genie_fleet_native call failed; falling back to Python")
        return None
    if len(result) != len(owners) or any(v < 0 or v >= len(TECH_INDEX) for v in result):
        return None
    if any(v == absent for v in result):
        return None
    return result, fuel_before, fuel_after


def try_native_optimize(
    absent_tech: str, use_native_flag: bool
) -> dict[str, object] | None:
    """Try one single-outage dispatch natively; None means use Python.

    Converts the seeded tasks to SoA lists (xs, ys, integer owners) and
    calls the ``genie_fleet_native`` extension ONLY when
    ``should_use_native(use_native_flag)`` is true; any other case —
    flag off, extension absent, unknown tech, extension mismatch —
    returns None so the caller falls back to the pure-Python core
    honestly. A non-None report is shaped by ``matrix.dispatch_report``,
    hence byte-equal to ``matrix.optimize()``.
    """
    if not should_use_native(use_native_flag):
        return None
    key = absent_tech.strip()
    if key not in TECH_INDEX:
        return None
    from genie_fleet.matrix import (
        Fleet,
        TaskRow,
        TaskStatus,
        dispatch_report,
        seed_fleet,
    )

    ext = _load_extension()
    if ext is None:
        return None
    before = seed_fleet()
    xs = [row.x for row in before.rows]
    ys = [row.y for row in before.rows]
    owners = [TECH_INDEX.index(row.assigned_tech) for row in before.rows]
    routed = _native_reassign(ext, xs, ys, owners, TECH_INDEX.index(key))
    if routed is None:
        return None
    result, native_before, native_after = routed
    after = Fleet(
        rows=tuple(
            row
            if TECH_INDEX[result[i]] == row.assigned_tech
            else TaskRow(
                task_id=row.task_id,
                x=row.x,
                y=row.y,
                priority=row.priority,
                zone=row.zone,
                assigned_tech=TECH_INDEX[result[i]],
                status=TaskStatus.REASSIGNED,
            )
            for i, row in enumerate(before.rows)
        )
    )
    report = dispatch_report(before, after, key)
    if report.get("tasks_moved") != owners.count(TECH_INDEX.index(key)):
        return None
    if report.get("fuel_before") != native_before:
        return None
    if report.get("fuel_after") != native_after:
        return None
    return report


def _native_arrow_reassign(
    ext: ModuleType,
    xs: Any,
    ys: Any,
    owners: Any,
    out: Any,
    absent: int,
) -> tuple[list[int], float, float] | None:
    """Call the extension over shared Arrow column buffers.

    Only the buffer views plus one int cross the boundary — no per-row
    lists or TaskRows. Returns ``(owners, fuel_before, fuel_after)``
    with fuels rounded to 2dp, or None on any absence/mismatch/failure
    so the caller falls back to Python honestly.
    """
    reassign = getattr(ext, "reassign_sick_leave_buffers", None)
    fuel = getattr(ext, "fleet_fuel_buffers", None)
    if not callable(reassign) or not callable(fuel):
        return None
    try:
        reassign(xs, ys, owners, absent, out)
        result = [int(v) for v in out]
        fuel_before = round(float(fuel(xs, ys, owners)), 2)
        fuel_after = round(float(fuel(xs, ys, out)), 2)
    except Exception:  # pragma: no cover - S4 suite proves the happy path
        _logger.warning("genie_fleet_native Arrow call failed; falling back")
        return None
    if len(result) != len(out):
        return None
    if any(v < 0 or v >= len(TECH_INDEX) for v in result):
        return None
    if any(v == absent for v in result):
        return None
    return result, fuel_before, fuel_after


def _arrow_seed_columns(
    pa: ModuleType,
) -> tuple[Any, Any, Any, Any, int] | None:
    """Build the seeded tasks as pyarrow columns plus typed buffer views.

    Returns ``(xs, ys, owners, out, count)`` where the first three are
    read-only views over the Arrow data buffers and ``out`` is a writable
    caller-owned int64 view for the indices. The caller's ``pa`` arrays
    stay alive via the views' buffer references. None on any failure.
    """
    from genie_fleet.matrix import seed_fleet

    try:
        before = seed_fleet()
        xs_buf = pa.array([row.x for row in before.rows], type=pa.float64()).buffers()[
            1
        ]
        ys_buf = pa.array([row.y for row in before.rows], type=pa.float64()).buffers()[
            1
        ]
        owners_buf = pa.array(
            [TECH_INDEX.index(row.assigned_tech) for row in before.rows],
            type=pa.int64(),
        ).buffers()[1]
        if xs_buf is None or ys_buf is None or owners_buf is None:
            return None
        count = len(before.rows)
        out_buf = pa.allocate_buffer(8 * count)
        columns = (
            memoryview(xs_buf).cast("d"),
            memoryview(ys_buf).cast("d"),
            memoryview(owners_buf).cast("q"),
            memoryview(out_buf).cast("q"),
            count,
        )
    except Exception:
        _logger.warning("Arrow column build failed; falling back to Python")
        return None
    return columns


def try_native_arrow_optimize(
    absent_tech: str, use_native_flag: bool
) -> dict[str, object] | None:
    """Try one single-outage dispatch over Arrow columns; None means Python.

    Builds the seeded tasks as pyarrow float64/int64 columns (pyarrow is
    resolved lazily so the repo env never needs it — it lives in an
    isolated prefix only), then calls the ``genie_fleet_native``
    extension ONLY when ``should_use_native(use_native_flag)`` is true.
    Any other case — flag off, extension absent, pyarrow absent, unknown
    tech, extension mismatch — returns None so the caller falls back to
    the pure-Python core honestly. A non-None report is shaped by
    ``matrix.dispatch_report``, hence byte-equal to ``matrix.optimize()``.
    """
    if not should_use_native(use_native_flag):
        return None
    key = absent_tech.strip()
    if key not in TECH_INDEX:
        return None
    try:
        pa = importlib.import_module("pyarrow")
    except ImportError:
        return None
    from genie_fleet.matrix import (
        Fleet,
        TaskRow,
        TaskStatus,
        dispatch_report,
        seed_fleet,
    )

    ext = _load_extension()
    if ext is None:
        return None
    built = _arrow_seed_columns(pa)
    if built is None:
        return None
    xs, ys, owners, out, _ = built
    before = seed_fleet()
    routed = _native_arrow_reassign(ext, xs, ys, owners, out, TECH_INDEX.index(key))
    if routed is None:
        return None
    result, native_before, native_after = routed
    after = Fleet(
        rows=tuple(
            row
            if TECH_INDEX[result[i]] == row.assigned_tech
            else TaskRow(
                task_id=row.task_id,
                x=row.x,
                y=row.y,
                priority=row.priority,
                zone=row.zone,
                assigned_tech=TECH_INDEX[result[i]],
                status=TaskStatus.REASSIGNED,
            )
            for i, row in enumerate(before.rows)
        )
    )
    report = dispatch_report(before, after, key)
    if report.get("tasks_moved") != [row.assigned_tech for row in before.rows].count(
        key
    ):
        return None
    if report.get("fuel_before") != native_before:
        return None
    if report.get("fuel_after") != native_after:
        return None
    return report
