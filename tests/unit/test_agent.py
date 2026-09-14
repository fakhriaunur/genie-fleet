"""Unit tests for the agent wrapper (offline path, no credentials)."""

from __future__ import annotations

from genie_fleet.agent import board_lines, parse_absent_tech, run_dispatch_request


def test_parse_absent_tech_names() -> None:
    assert parse_absent_tech("Rio called in sick today") == "Rio"
    assert parse_absent_tech("sam is out") == "Sam"
    assert parse_absent_tech("someone is sick") == "Maya"


def test_run_dispatch_request_offline_shape() -> None:
    outcome = run_dispatch_request("Maya called in sick")
    assert outcome["absent_tech"] == "Maya"
    assert "path" in outcome
    report = outcome["report"]
    assert isinstance(report, dict)
    assert report["tasks_total"] == 6
    board = outcome["board"]
    assert isinstance(board, list) and len(board) == 3  # header + 2 moved
    assert board_lines(report) == board
