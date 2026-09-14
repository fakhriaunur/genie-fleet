"""Unit tests for the mocked dispatch matrix (pure core, no I/O)."""

from __future__ import annotations

import pytest

from genie_fleet.matrix import (
    TECH_HOME,
    Fleet,
    TaskRow,
    TaskStatus,
    dispatch_report,
    fleet_fuel,
    optimize,
    reassign_sick_leave,
    seed_fleet,
)


def test_seed_has_six_tasks_two_per_tech() -> None:
    fleet = seed_fleet()
    assert len(fleet.rows) == 6
    counts: dict[str, int] = {}
    for row in fleet.rows:
        counts[row.assigned_tech] = counts.get(row.assigned_tech, 0) + 1
    assert counts == {"Maya": 2, "Rio": 2, "Sam": 2}


def test_reassign_moves_only_absent_tech_tasks() -> None:
    before = seed_fleet()
    after = reassign_sick_leave(before, "Maya")
    assert len(after.rows) == 6
    for row in after.rows:
        assert row.assigned_tech != "Maya"
    untouched = [row for row in after.rows if row.status == TaskStatus.ASSIGNED]
    assert len(untouched) == 4
    moved = [row for row in after.rows if row.status == TaskStatus.REASSIGNED]
    assert len(moved) == 2
    # Nearest-cover split: task 0 → Rio, task 1 → Sam.
    assert after.by_id(0).assigned_tech == "Rio"
    assert after.by_id(1).assigned_tech == "Sam"


def test_reassign_unknown_tech_raises() -> None:
    with pytest.raises(ValueError, match="unknown tech"):
        reassign_sick_leave(seed_fleet(), "Zed")


def test_reassign_preserves_task_ids_and_coords() -> None:
    before = seed_fleet()
    after = reassign_sick_leave(before, "Rio")
    assert sorted(row.task_id for row in after.rows) == list(range(6))
    for row in after.rows:
        original = before.by_id(row.task_id)
        assert (row.x, row.y) == (original.x, original.y)
        assert row.priority == original.priority


def test_fuel_increases_and_report_accounts() -> None:
    before = seed_fleet()
    after = reassign_sick_leave(before, "Maya")
    assert fleet_fuel(after) > fleet_fuel(before)
    report = dispatch_report(before, after, "Maya")
    assert report["tasks_total"] == 6
    assert report["tasks_moved"] == 2
    assert report["added_fuel"] == round(
        float(report["fuel_after"]) - float(report["fuel_before"]), 2
    )


def test_optimize_canned_scenario() -> None:
    report = optimize("Maya")
    assert report["mode"] == "mocked"
    assert report["absent_tech"] == "Maya"
    assert report["tasks_moved"] == 2


def test_row_validation() -> None:
    with pytest.raises(ValueError, match="unknown tech"):
        TaskRow(task_id=9, x=0.0, y=0.0, priority=3, zone="z", assigned_tech="Zed")
    with pytest.raises(ValueError, match="priority"):
        TaskRow(task_id=9, x=0.0, y=0.0, priority=9, zone="z", assigned_tech="Maya")


def test_duplicate_task_ids_rejected() -> None:
    row = TaskRow(task_id=0, x=0.0, y=0.0, priority=3, zone="z", assigned_tech="Maya")
    with pytest.raises(ValueError, match="duplicate task_id"):
        Fleet(rows=(row, row))


def test_all_three_outages_coverable() -> None:
    for tech in TECH_HOME:
        after = reassign_sick_leave(seed_fleet(), tech)
        assert all(row.assigned_tech != tech for row in after.rows)
        assert len(after.rows) == 6
