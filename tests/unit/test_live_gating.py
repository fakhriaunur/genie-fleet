"""Live gating + fallback tests (mocked live path, no credentials, no spend).

VAL-LIVE-003: mock mode always takes the direct-tool offline path, even
when the Strands SDK is importable.
VAL-LIVE-004: a failed live attempt still returns the correct Maya report
(2 moved / 6 total) with an honest path label recording the live failure
(contains both "live" and "direct-tool"; never a bare direct-tool label).
VAL-SCALE-008: the multi-outage path honors the same is_live AND
STRANDS_AVAILABLE gate — mock stays direct-tool, live with the mocked SDK
attempts the Agent and falls back honestly on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi.testclient import TestClient
from pytest import LogCaptureFixture, MonkeyPatch

import genie_fleet.agent as agent_module
from genie_fleet.agent import run_dispatch_request, run_multi_dispatch_request
from genie_fleet.api import create_app
from genie_fleet.settings import Settings

MOCK_SETTINGS = Settings(mode="mock")
LIVE_SETTINGS = Settings(mode="live", strands_model_id="test-model-id")


def test_mock_never_attempts_live_even_when_sdk_importable(
    monkeypatch: MonkeyPatch,
) -> None:
    """Mock mode stays on direct-tool even with the SDK importable."""
    calls: list[str] = []

    def _spy(text: str, settings: Settings | None = None) -> dict[str, Any]:
        calls.append(text)
        raise AssertionError("live path must not run in mock mode")

    monkeypatch.setattr(agent_module, "STRANDS_AVAILABLE", True)
    monkeypatch.setattr(agent_module, "run_with_strands", _spy)
    outcome = run_dispatch_request("Maya called in sick", settings=MOCK_SETTINGS)
    assert str(outcome["path"]).startswith("direct-tool")
    assert calls == []
    report = outcome["report"]
    assert isinstance(report, dict)
    assert report["tasks_moved"] == 2
    assert report["tasks_total"] == 6


def test_mock_dispatch_endpoint_stays_direct_tool(monkeypatch: MonkeyPatch) -> None:
    """Mock-mode POST /dispatch takes the offline path regardless of SDK."""
    monkeypatch.setattr(agent_module, "STRANDS_AVAILABLE", True)
    client = TestClient(create_app(Settings(mode="mock")))
    response = client.post("/dispatch", json={"absent_tech": "Maya"})
    assert response.status_code == 200
    body = response.json()
    assert str(body["path"]).startswith("direct-tool")
    assert body["report"]["tasks_moved"] == 2
    assert body["report"]["tasks_total"] == 6


def test_live_failure_falls_through_with_honest_path(
    monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """A mocked-Agent failure keeps the Maya 2/6 report, honestly labeled."""
    logged_before = len(caplog.records)

    def _boom(text: str, settings: Settings | None = None) -> dict[str, Any]:
        raise RuntimeError("simulated Bedrock outage")

    monkeypatch.setattr(agent_module, "STRANDS_AVAILABLE", True)
    monkeypatch.setattr(agent_module, "run_with_strands", _boom)
    with caplog.at_level(logging.WARNING, logger="genie_fleet.agent"):
        outcome = run_dispatch_request("Maya called in sick", settings=LIVE_SETTINGS)
    path = str(outcome["path"])
    assert "live" in path
    assert "direct-tool" in path
    assert path != "direct-tool"
    assert not path.startswith("direct-tool")
    report = outcome["report"]
    assert isinstance(report, dict)
    assert report["absent_tech"] == "Maya"
    assert report["tasks_moved"] == 2
    assert report["tasks_total"] == 6
    new_records = caplog.records[logged_before:]
    assert any("live" in r.getMessage().lower() for r in new_records)


def test_multi_mock_never_attempts_live_even_when_sdk_importable(
    monkeypatch: MonkeyPatch,
) -> None:
    """Mock-mode absent_techs stays on direct-tool even with SDK importable."""
    calls: list[str] = []

    def _spy(text: str, settings: Settings | None = None) -> dict[str, Any]:
        calls.append(text)
        raise AssertionError("live path must not run in mock mode")

    monkeypatch.setattr(agent_module, "STRANDS_AVAILABLE", True)
    monkeypatch.setattr(agent_module, "run_with_strands", _spy)
    outcome = run_multi_dispatch_request(["Maya", "Rio"], settings=MOCK_SETTINGS)
    assert str(outcome["path"]).startswith("direct-tool")
    assert calls == []
    report = outcome["report"]
    assert isinstance(report, dict)
    assert report["tasks_moved"] == 4
    assert report["tasks_total"] == 6


def test_multi_live_failure_falls_through_with_honest_path(
    monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """A mocked-Agent failure keeps the Maya+Rio 4/6 report, honestly labeled."""
    logged_before = len(caplog.records)
    calls: list[str] = []

    def _boom(text: str, settings: Settings | None = None) -> dict[str, Any]:
        calls.append(text)
        raise RuntimeError("simulated Bedrock outage")

    monkeypatch.setattr(agent_module, "STRANDS_AVAILABLE", True)
    monkeypatch.setattr(agent_module, "run_with_strands", _boom)
    with caplog.at_level(logging.WARNING, logger="genie_fleet.agent"):
        outcome = run_multi_dispatch_request(["Maya", "Rio"], settings=LIVE_SETTINGS)
    assert calls != []
    path = str(outcome["path"])
    assert "live" in path
    assert "direct-tool" in path
    assert not path.startswith("direct-tool")
    report = outcome["report"]
    assert isinstance(report, dict)
    assert report["tasks_moved"] == 4
    assert report["tasks_total"] == 6
    new_records = caplog.records[logged_before:]
    assert any("live" in r.getMessage().lower() for r in new_records)
