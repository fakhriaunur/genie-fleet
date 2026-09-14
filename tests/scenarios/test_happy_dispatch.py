"""Happy-path outage scenarios (shells only, mock mode, $0 spend).

Outage table (deterministic values from the pure matrix core,
asserted exactly below via the HTTP shell)::

    | absent | moved/total | fuel_before | fuel_after | added_fuel | cover split        |
    | Maya   | 2 / 6       | 12.7        | 22.43      | 9.73       | task 0 -> Rio, 1 -> Sam |
    | Rio    | 2 / 6       | 12.7        | 29.28      | 16.59      | tasks 2, 3 -> Maya |
    | Sam    | 2 / 6       | 12.7        | 29.28      | 16.59      | tasks 4, 5 -> Maya |

Shells only: FastAPI TestClient (no sockets, no credentials). Does not
touch the pure core, TECH_HOME, the report shape, or replay goldens.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from genie_fleet.api import create_app
from genie_fleet.settings import Settings

client = TestClient(create_app(Settings(mode="mock")))


def test_maya_dispatch_returns_canned_report() -> None:
    response = client.post("/dispatch", json={"absent_tech": "Maya"})
    assert response.status_code == 200
    body = response.json()
    report = body["report"]
    assert report["tasks_moved"] == 2
    assert report["tasks_total"] == 6
    assert report["fuel_before"] == 12.7
    assert report["fuel_after"] == 22.43
    assert report["added_fuel"] == 9.73
    board = body["board"]
    assert len(board) == 3  # header + 2 moved-task lines
    assert "absent: Maya" in board[0]
    assert "12.7" in board[0] and "22.43" in board[0]


def test_rio_dispatch_returns_deterministic_report() -> None:
    response = client.post("/dispatch", json={"absent_tech": "Rio"})
    assert response.status_code == 200
    report = response.json()["report"]
    assert report["absent_tech"] == "Rio"
    assert report["tasks_moved"] == 2
    assert report["tasks_total"] == 6
    assert report["fuel_before"] == 12.7
    assert report["fuel_after"] == 29.28
    assert report["added_fuel"] == 16.59


def test_sam_dispatch_returns_deterministic_report() -> None:
    response = client.post("/dispatch", json={"absent_tech": "Sam"})
    assert response.status_code == 200
    report = response.json()["report"]
    assert report["absent_tech"] == "Sam"
    assert report["tasks_moved"] == 2
    assert report["tasks_total"] == 6
    assert report["fuel_before"] == 12.7
    assert report["fuel_after"] == 29.28
    assert report["added_fuel"] == 16.59


def test_repeat_calls_return_identical_reports() -> None:
    for absent in ("Maya", "Rio", "Sam"):
        first = client.post("/dispatch", json={"absent_tech": absent}).json()
        second = client.post("/dispatch", json={"absent_tech": absent}).json()
        assert first["report"] == second["report"]
        assert first["board"] == second["board"]
