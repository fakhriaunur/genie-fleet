"""Live model wiring + boot gate tests (mocked SDK, no network, no spend).

VAL-LIVE-002: GENIE_MODE=live with an empty STRANDS_MODEL_ID refuses
fail-closed before serving any request.
VAL-LIVE-005: the live path constructs the Strands Agent on the Bedrock
provider path with the configured model id and the ap-southeast-3 region
(asserted via mocked-Agent constructor arguments).
VAL-LIVE-006: GET /ready in mock mode reports mode mock with
optimize_dispatch metadata and zero key material.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import genie_fleet.agent as agent_module
from genie_fleet.agent import run_dispatch_request
from genie_fleet.api import create_app
from genie_fleet.settings import Settings, load_settings
from genie_fleet.tools import optimize_dispatch

MODEL_CANARY = "test-model-id-xyz"
READY_CANARY = "canary-model-id-12345"


def _install_fake_strands(
    monkeypatch: MonkeyPatch,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Install fake `strands` + `strands.models` modules; record ctors."""
    bedrock_calls: list[dict[str, Any]] = []
    agent_calls: list[dict[str, Any]] = []

    class FakeBedrockModel:
        def __init__(self, **kwargs: Any) -> None:
            bedrock_calls.append(kwargs)

    class FakeAgent:
        def __init__(self, **kwargs: Any) -> None:
            agent_calls.append(kwargs)

        def __call__(self, prompt: str) -> str:
            return f"mocked-agent-response to: {prompt[:24]}"

    strands_module = types.ModuleType("strands")
    models_module = types.ModuleType("strands.models")
    models_module.BedrockModel = FakeBedrockModel  # type: ignore[attr-defined]
    strands_module.Agent = FakeAgent  # type: ignore[attr-defined]
    strands_module.models = models_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "strands", strands_module)
    monkeypatch.setitem(sys.modules, "strands.models", models_module)
    return bedrock_calls, agent_calls


def test_live_constructs_agent_with_configured_model_and_region(
    monkeypatch: MonkeyPatch,
) -> None:
    """Mocked-Agent ctor receives the model id and ap-southeast-3 region."""
    bedrock_calls, agent_calls = _install_fake_strands(monkeypatch)
    monkeypatch.setattr(agent_module, "STRANDS_AVAILABLE", True)
    settings = Settings(mode="live", strands_model_id=MODEL_CANARY)
    assert settings.aws_region == "ap-southeast-3"

    outcome = run_dispatch_request("Maya called in sick", settings=settings)

    assert outcome["path"] == "strands-agent"
    assert len(bedrock_calls) == 1
    assert bedrock_calls[0]["model_id"] == MODEL_CANARY
    assert bedrock_calls[0]["region_name"] == "ap-southeast-3"
    assert len(agent_calls) == 1
    assert agent_calls[0]["tools"] == [optimize_dispatch]
    assert agent_calls[0]["model"] is not None
    report = outcome["report"]
    assert isinstance(report, dict)
    assert report["tasks_moved"] == 2
    assert report["tasks_total"] == 6


def test_live_boot_refuses_without_model_id() -> None:
    """Settings fail closed when live mode has no model id."""
    with pytest.raises(RuntimeError, match="STRANDS_MODEL_ID"):
        Settings(mode="live", strands_model_id="")


def test_live_load_settings_refuses_without_model_id() -> None:
    """Env-loaded settings fail closed on live mode with empty model id."""
    with pytest.raises(RuntimeError, match="STRANDS_MODEL_ID"):
        load_settings({"GENIE_MODE": "live", "STRANDS_MODEL_ID": ""})


def test_live_app_factory_refuses_before_serving(
    monkeypatch: MonkeyPatch,
) -> None:
    """create_app raises before serving when live boot lacks a model id."""
    monkeypatch.setenv("GENIE_MODE", "live")
    monkeypatch.setenv("STRANDS_MODEL_ID", "")
    with pytest.raises(RuntimeError, match="STRANDS_MODEL_ID"):
        create_app()


def test_ready_mock_reports_tool_metadata_without_key_material() -> None:
    """GET /ready in mock mode: mock + tool metadata, no key material."""
    client = TestClient(
        create_app(Settings(mode="mock", strands_model_id=READY_CANARY))
    )
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "mock"
    assert body["tool"]["tool_name"] == "optimize_dispatch"
    assert READY_CANARY not in response.text
    lowered = response.text.lower()
    assert "aws_secret" not in lowered
    assert "aws_access" not in lowered
    assert "api_key" not in lowered
