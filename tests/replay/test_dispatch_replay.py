"""Replay test: canned sick-leave report must match the golden fixture."""

from __future__ import annotations

import json
from pathlib import Path

from genie_fleet.agent import run_dispatch_request

FIXTURE = Path(__file__).parent / "fixtures" / "dispatch_golden.json"


def test_dispatch_replay_matches_golden() -> None:
    outcome = run_dispatch_request("Maya called in sick")
    golden = json.loads(FIXTURE.read_text())
    assert outcome["absent_tech"] == golden["absent_tech"]
    assert outcome["report"] == golden["report"]
