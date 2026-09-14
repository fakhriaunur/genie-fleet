"""M2 parity: native shim stays off; flag-on falls back byte-identical."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from genie_fleet import _native as native_shim
from genie_fleet.matrix import TECH_HOME, optimize
from genie_fleet.settings import load_settings

GOLDEN = Path(__file__).parent.parent / "replay" / "fixtures" / "dispatch_golden.json"


def test_native_unavailable_in_this_env() -> None:
    assert native_shim.NATIVE_AVAILABLE is False


def test_native_flag_defaults_off() -> None:
    assert load_settings({}).use_native is False
    assert native_shim.should_use_native(False) is False


def test_native_flag_parses_opt_in() -> None:
    assert load_settings({"GENIE_NATIVE": "1"}).use_native is True
    assert load_settings({"GENIE_NATIVE": "0"}).use_native is False


def test_flag_on_falls_back_to_identical_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GENIE_NATIVE", "1")
    requested = load_settings()
    assert requested.use_native is True
    # Requested but absent: fail-safe fallback, never a crash.
    assert native_shim.should_use_native(requested.use_native) is False
    expected = {tech: optimize(tech) for tech in TECH_HOME}
    monkeypatch.setenv("GENIE_NATIVE", "0")
    assert load_settings().use_native is False
    for tech in TECH_HOME:
        assert optimize(tech) == expected[tech]


def test_golden_fixture_still_matches() -> None:
    golden = json.loads(GOLDEN.read_text())
    assert optimize("Maya") == golden["report"]


def test_fallback_warns_at_most_once(caplog: pytest.LogCaptureFixture) -> None:
    native_shim._warned_fallback = False
    with caplog.at_level(logging.WARNING, logger="genie_fleet.native"):
        assert native_shim.should_use_native(True) is False
        assert native_shim.should_use_native(True) is False
    warnings = [
        record
        for record in caplog.records
        if record.name == "genie_fleet.native" and record.levelno >= logging.WARNING
    ]
    assert len(warnings) == 1
