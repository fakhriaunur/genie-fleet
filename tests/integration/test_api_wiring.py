"""API wiring tests (FastAPI TestClient, no sockets, no credentials)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from genie_fleet.api import create_app
from genie_fleet.settings import Settings

client = TestClient(create_app(Settings(mode="mock")))


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("X-Request-Id")


def test_ready_reports_mock_and_tool() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "mock"
    assert body["tool"]["tool_name"] == "optimize_dispatch"


def test_dispatch_sick_leave() -> None:
    response = client.post("/dispatch", json={"absent_tech": "Maya"})
    assert response.status_code == 200
    body = response.json()
    assert body["absent_tech"] == "Maya"
    assert body["report"]["tasks_moved"] == 2
    assert len(body["board"]) == 3


def test_dispatch_unknown_tech() -> None:
    response = client.post("/dispatch", json={"absent_tech": "Zed"})
    assert response.status_code == 200
    assert "unknown tech" in response.json()["error"]
