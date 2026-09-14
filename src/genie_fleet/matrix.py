"""Mocked dispatch matrix — pure deterministic core (no I/O, no network).

Worksheet contract: parallel arrays of task_ids with coordinates, priorities,
zones, assignments, and statuses. Tonight the arrays are plain Python; the
zero-copy Arrow / C++ pybind11 path is a documented stretch, not a claim.

Fuel model: each task costs the Euclidean distance from its assigned tech's
home base. Sick-leave re-routing reassigns every task of the absent tech to
the available tech with the smallest added distance (greedy, deterministic,
ties broken by tech name). All tasks are preserved; nothing is dropped.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

#: Home bases per tech: the distance anchor for the fuel model.
TECH_HOME: dict[str, tuple[float, float]] = {
    "Maya": (0.0, 0.0),
    "Rio": (10.0, 0.0),
    "Sam": (0.0, 10.0),
}

#: Canonical demo scenario: Maya calls in sick, her district must be covered.
CANNED_ABSENT_TECH = "Maya"


class TaskStatus(StrEnum):
    """Lifecycle of one matrix row."""

    ASSIGNED = "assigned"
    REASSIGNED = "reassigned"


@dataclass(frozen=True)
class TaskRow:
    """One service task. Immutable; transitions return new rows."""

    task_id: int
    x: float
    y: float
    priority: int
    zone: str
    assigned_tech: str
    status: TaskStatus = TaskStatus.ASSIGNED

    def __post_init__(self) -> None:
        if isinstance(self.task_id, bool) or not isinstance(self.task_id, int):
            raise ValueError(f"task_id must be an int, got: {self.task_id!r}")
        if self.task_id < 0:
            raise ValueError(f"task_id must be non-negative, got: {self.task_id}")
        for name, value in (("x", self.x), ("y", self.y)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number, got: {value!r}")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite, got: {value!r}")
        if not 1 <= self.priority <= 5:
            raise ValueError(f"priority out of 1..5 range: {self.priority}")
        if not self.zone:
            raise ValueError("zone must be non-empty")
        if self.assigned_tech not in TECH_HOME:
            raise ValueError(f"unknown tech: {self.assigned_tech!r}")
        if not isinstance(self.status, TaskStatus):
            raise ValueError(f"status must be a TaskStatus, got: {self.status!r}")


@dataclass(frozen=True)
class Fleet:
    """The dispatcher view: one row per service task."""

    rows: tuple[TaskRow, ...]

    def __post_init__(self) -> None:
        seen: set[int] = set()
        for row in self.rows:
            if row.task_id in seen:
                raise ValueError(f"duplicate task_id: {row.task_id}")
            seen.add(row.task_id)

    def by_id(self, task_id: int) -> TaskRow:
        """Fetch a row by task_id or raise ValueError on unknown ids."""
        for row in self.rows:
            if row.task_id == task_id:
                return row
        raise ValueError(f"unknown task_id: {task_id}")


def seed_fleet() -> Fleet:
    """Build the canonical 6-task morning board. Deterministic; no randomness."""
    return Fleet(
        rows=(
            TaskRow(
                task_id=0, x=2.0, y=1.0, priority=5, zone="north", assigned_tech="Maya"
            ),
            TaskRow(
                task_id=1, x=1.0, y=3.0, priority=4, zone="north", assigned_tech="Maya"
            ),
            TaskRow(
                task_id=2, x=9.0, y=1.0, priority=3, zone="east", assigned_tech="Rio"
            ),
            TaskRow(
                task_id=3, x=11.0, y=2.0, priority=4, zone="east", assigned_tech="Rio"
            ),
            TaskRow(
                task_id=4, x=1.0, y=9.0, priority=5, zone="west", assigned_tech="Sam"
            ),
            TaskRow(
                task_id=5, x=2.0, y=11.0, priority=2, zone="west", assigned_tech="Sam"
            ),
        )
    )


def distance(x: float, y: float, tech: str) -> float:
    """Euclidean distance from a point to a tech's home base."""
    home_x, home_y = TECH_HOME[tech]
    return math.hypot(x - home_x, y - home_y)


def fleet_fuel(fleet: Fleet) -> float:
    """Total fuel: sum of per-task distances from each assigned tech's base."""
    return sum(distance(row.x, row.y, row.assigned_tech) for row in fleet.rows)


def nearest_cover(row: TaskRow, available: list[str]) -> str:
    """Pick the available tech closest to the task (ties broken by name)."""
    return min(available, key=lambda tech: (distance(row.x, row.y, tech), tech))


def reassign_sick_leave(fleet: Fleet, absent_tech: str) -> Fleet:
    """Re-route one tech's district across the remaining crew. Pure.

    Every task owned by ``absent_tech`` moves to the nearest available tech
    and is marked REASSIGNED; all other rows are untouched. Raises
    ValueError for unknown techs or a last-crew-member outage (refuses to
    silently drop tasks instead of guessing).
    """
    if absent_tech not in TECH_HOME:
        raise ValueError(f"unknown tech: {absent_tech!r}")
    available = sorted(tech for tech in TECH_HOME if tech != absent_tech)
    if not available:
        raise ValueError("no covering crew available; refusing to drop tasks")
    rows: list[TaskRow] = []
    for row in fleet.rows:
        if row.assigned_tech != absent_tech or row.status == TaskStatus.REASSIGNED:
            rows.append(row)
            continue
        cover = nearest_cover(row, available)
        rows.append(
            TaskRow(
                task_id=row.task_id,
                x=row.x,
                y=row.y,
                priority=row.priority,
                zone=row.zone,
                assigned_tech=cover,
                status=TaskStatus.REASSIGNED,
            )
        )
    return Fleet(rows=tuple(rows))


def dispatch_report(
    fleet_before: Fleet, fleet_after: Fleet, absent_tech: str
) -> dict[str, object]:
    """JSON-serializable before/after report with fuel accounting."""
    fuel_before = fleet_fuel(fleet_before)
    fuel_after = fleet_fuel(fleet_after)
    moved = [
        {
            "task_id": row.task_id,
            "from": fleet_before.by_id(row.task_id).assigned_tech,
            "to": row.assigned_tech,
            "zone": row.zone,
            "priority": row.priority,
        }
        for row in fleet_after.rows
        if row.status == TaskStatus.REASSIGNED
    ]
    board = [
        {
            "task_id": row.task_id,
            "tech": row.assigned_tech,
            "status": row.status.value,
            "zone": row.zone,
            "priority": row.priority,
        }
        for row in fleet_after.rows
    ]
    return {
        "mode": "mocked",
        "absent_tech": absent_tech,
        "fuel_before": round(fuel_before, 2),
        "fuel_after": round(fuel_after, 2),
        "added_fuel": round(fuel_after - fuel_before, 2),
        "tasks_moved": len(moved),
        "tasks_total": len(fleet_after.rows),
        "moved": moved,
        "board": board,
    }


def optimize(absent_tech: str = CANNED_ABSENT_TECH) -> dict[str, object]:
    """One-call optimizer: seed board → sick-leave re-route → report. Pure."""
    before = seed_fleet()
    after = reassign_sick_leave(before, absent_tech)
    return dispatch_report(before, after, absent_tech)
