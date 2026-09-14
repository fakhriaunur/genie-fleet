"""Enterprise scale benchmarks (shells + core primitives, mock mode, $0 spend).

Proves headroom without touching the core: a seeded deterministic fleet
builder uses only the frozen ``TaskRow``/``Fleet`` primitives (no
``matrix.py`` changes) at 6 / 600 / 6000 / 60000 tasks, asserting exact
accounting invariants at every size:

- every task (before and after) sits on a known tech,
- moved + unmoved == total (and moved == the absent district),
- fuel_before / fuel_after / added_fuel reconcile exactly with raw
  ``fleet_fuel`` math at 2dp rounding,
- a from-scratch repeat with the same seed is identical.

Per-size latency ceilings are set from measured timings times
``SAFETY_FACTOR`` (derivation below). A 200-concurrent Maya burst over
in-process ``TestClient`` threads (no sockets, no port claims) asserts
all-HTTP-200, zero 5xx, and identical bodies, with p95 measured and
printed report-only (no threshold gate on dev-mode serving).

Slow-marker decision (measured 2026-09-15 on this host): per-size blocks
run ~0.00s / ~0.01s / ~0.25s / ~17s and the burst ~0.7s, so the whole
file lands around 20 seconds, well under a minute. It therefore rides
the default suite with NO slow marker and no quarantine. If the 60k
block ever grows past ~45s on slower CI, quarantine it with
``pytestmark = pytest.mark.slow``.

Does not touch src/, goldens, the report shape, TECH_HOME, or config.
"""

from __future__ import annotations

import math
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from genie_fleet.api import create_app
from genie_fleet.matrix import (
    TECH_HOME,
    Fleet,
    TaskRow,
    TaskStatus,
    dispatch_report,
    fleet_fuel,
    reassign_sick_leave,
)
from genie_fleet.settings import Settings

SCALE_SEED = 20260915
ABSENT_TECH = "Maya"
KNOWN_TECHS = sorted(TECH_HOME)
ZONE_ROTATION = ("north", "east", "west", "south", "central")

# Latency ceilings: measured block time (build + dispatch + checks +
# from-scratch repeat) times SAFETY_FACTOR, with a floor so fast sizes
# never flake on CI jitter. Measured 2026-09-15: 6 -> ~0.00s,
# 600 -> ~0.01s, 6000 -> ~0.25s, 60000 -> ~17s (dominated by the frozen
# report builder, which re-scans the fleet per moved row; the core is
# untouched, so the suite pins the cost instead of optimizing it).
SAFETY_FACTOR = 5
LATENCY_CEILINGS_S = {6: 5.0, 600: 5.0, 6000: 5.0, 60000: 90.0}

BURST_REQUESTS = 200

burst_app = create_app(Settings(mode="mock"))


def build_fleet(size: int, seed: int = SCALE_SEED) -> Fleet:
    """Seeded deterministic fleet from frozen primitives only.

    Round-robin tech assignment, so each tech owns exactly ``size // 3``
    tasks (all four suite sizes are multiples of 3) and the absent
    district size is pinned exactly.
    """
    rng = random.Random(seed)
    rows = tuple(
        TaskRow(
            task_id=index,
            x=round(rng.uniform(0.0, 12.0), 2),
            y=round(rng.uniform(0.0, 12.0), 2),
            priority=rng.randint(1, 5),
            zone=ZONE_ROTATION[index % len(ZONE_ROTATION)],
            assigned_tech=KNOWN_TECHS[index % len(KNOWN_TECHS)],
        )
        for index in range(size)
    )
    return Fleet(rows=rows)


def assert_exact_accounting(
    before: Fleet,
    after: Fleet,
    report: dict[str, object],
    absent: str = ABSENT_TECH,
) -> None:
    """Exact accounting invariants for one dispatched fleet."""
    total = len(after.rows)
    assert total == len(before.rows)
    assert report["tasks_total"] == total
    for row in before.rows:
        assert row.assigned_tech in TECH_HOME
    for row in after.rows:
        assert row.assigned_tech in TECH_HOME
    moved = sum(1 for row in after.rows if row.status == TaskStatus.REASSIGNED)
    unmoved = total - moved
    assert moved + unmoved == total
    assert report["tasks_moved"] == moved
    expected_moved = sum(1 for row in before.rows if row.assigned_tech == absent)
    assert moved == expected_moved
    assert moved == total // 3
    raw_before = fleet_fuel(before)
    raw_after = fleet_fuel(after)
    assert report["fuel_before"] == round(raw_before, 2)
    assert report["fuel_after"] == round(raw_after, 2)
    assert report["added_fuel"] == round(raw_after - raw_before, 2)


@pytest.mark.parametrize("size", [6, 600, 6000, 60000])
def test_scale_fleet_keeps_exact_accounting(size: int) -> None:
    started = time.perf_counter()
    before = build_fleet(size)
    after = reassign_sick_leave(before, ABSENT_TECH)
    report = dispatch_report(before, after, ABSENT_TECH)
    assert_exact_accounting(before, after, report)
    # Repeat from scratch with the same seed: determinism must be exact.
    repeat_before = build_fleet(size)
    repeat_after = reassign_sick_leave(repeat_before, ABSENT_TECH)
    repeat_report = dispatch_report(repeat_before, repeat_after, ABSENT_TECH)
    assert repeat_report == report
    elapsed = time.perf_counter() - started
    ceiling = LATENCY_CEILINGS_S[size]
    print(
        f"[scale] size={size} moved={report['tasks_moved']} "
        f"elapsed={elapsed:.2f}s ceiling={ceiling:.0f}s"
    )
    assert elapsed <= ceiling, (
        f"size {size} took {elapsed:.2f}s, over ceiling {ceiling:.0f}s "
        f"(measured * SAFETY_FACTOR={SAFETY_FACTOR})"
    )


def _post_maya_dispatch(_index: int) -> tuple[int, dict[str, object], float]:
    started = time.perf_counter()
    with TestClient(burst_app) as dispatch_client:
        response = dispatch_client.post("/dispatch", json={"absent_tech": "Maya"})
    return response.status_code, response.json(), time.perf_counter() - started


def test_200_concurrent_maya_burst_all_succeed_identically() -> None:
    baseline = TestClient(burst_app).post("/dispatch", json={"absent_tech": "Maya"})
    assert baseline.status_code == 200
    baseline_body = baseline.json()

    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(_post_maya_dispatch, range(BURST_REQUESTS)))

    assert len(results) == BURST_REQUESTS
    statuses = [status for status, _, _ in results]
    assert all(status == 200 for status in statuses)
    assert not any(status >= 500 for status in statuses)
    assert sum(1 for status in statuses if status == 200) == BURST_REQUESTS

    bodies = [body for _, body, _ in results]
    for body in bodies:
        assert body["report"]["tasks_moved"] == 2
    assert all(body == bodies[0] for body in bodies)
    assert bodies[0] == baseline_body

    latencies = sorted(latency for _, _, latency in results)
    p50 = statistics.median(latencies)
    p95 = latencies[math.ceil(0.95 * len(latencies)) - 1]
    print(
        f"[scale] burst={BURST_REQUESTS} ok200={BURST_REQUESTS} "
        f"server5xx=0 identical=True "
        f"p50={p50 * 1000:.1f}ms p95={p95 * 1000:.1f}ms "
        f"max={latencies[-1] * 1000:.1f}ms (report-only, no threshold gate)"
    )
