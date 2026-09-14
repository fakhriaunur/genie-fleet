"""Multi-outage dispatch scenarios (additive API extension, mock mode, $0).

POST /dispatch accepts an optional ``absent_techs`` array. When absent or
empty, the singular ``absent_tech`` path runs unchanged (byte-identical to
the golden). When non-empty, the union of the absent districts is
re-routed via existing core primitives. An unknown tech anywhere in the
list keeps the HTTP-200 error-body quirk (asserted, not changed).

Shells only: FastAPI TestClient (no sockets, no credentials). Does not
touch TECH_HOME, fuel math/rounding, the singular report shape, or the
replay golden.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from genie_fleet.api import create_app
from genie_fleet.matrix import TECH_HOME, fleet_fuel, seed_fleet
from genie_fleet.settings import Settings

client = TestClient(create_app(Settings(mode="mock")))


def test_maya_rio_outage_reroutes_union_of_both_districts() -> None:
    response = client.post("/dispatch", json={"absent_techs": ["Maya", "Rio"]})
    assert response.status_code == 200
    body = response.json()
    report = body["report"]
    assert report["tasks_total"] == 6
    # Union of the Maya district (2 tasks) and the Rio district (2 tasks).
    assert report["tasks_moved"] == 4
    # Only Sam remains to cover, so every task sits on Sam.
    techs_after = {row["tech"] for row in report["board"]}
    assert techs_after == {"Sam"}
    for row in report["board"]:
        assert row["tech"] in TECH_HOME
    moved_froms = sorted(entry["from"] for entry in report["moved"])
    assert moved_froms == ["Maya", "Maya", "Rio", "Rio"]
    assert all(entry["to"] == "Sam" for entry in report["moved"])
    # Exact fuel reconciliation against the frozen fuel math.
    before = seed_fleet()
    assert report["fuel_before"] == round(fleet_fuel(before), 2)
    assert report["fuel_before"] == 12.7
    assert report["fuel_after"] == 46.27
    assert report["added_fuel"] == 33.57
    assert report["added_fuel"] == round(
        report["fuel_after"] - report["fuel_before"], 2
    )
    assert len(body["board"]) == 5  # header + 4 moved-task lines


def test_multi_outage_repeats_are_identical() -> None:
    first = client.post("/dispatch", json={"absent_techs": ["Maya", "Rio"]}).json()
    second = client.post("/dispatch", json={"absent_techs": ["Rio", "Maya"]}).json()
    assert first["report"] == second["report"]
    assert first["board"] == second["board"]


def test_unknown_tech_anywhere_keeps_200_error_quirk() -> None:
    response = client.post("/dispatch", json={"absent_techs": ["Maya", "Zed"]})
    assert response.status_code == 200
    body = response.json()
    assert "Zed" in body["error"]
    assert body["known_techs"] == ["Maya", "Rio", "Sam"]
    assert "report" not in body


def test_empty_absent_techs_falls_back_to_singular_path() -> None:
    response = client.post(
        "/dispatch", json={"absent_tech": "Maya", "absent_techs": []}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["absent_tech"] == "Maya"
    assert body["report"]["tasks_moved"] == 2
    assert body["report"]["tasks_total"] == 6
    assert body["report"]["fuel_before"] == 12.7
    assert body["report"]["fuel_after"] == 22.43


def test_missing_absent_techs_uses_singular_path() -> None:
    response = client.post("/dispatch", json={"absent_tech": "Maya"})
    assert response.status_code == 200
    assert response.json()["report"]["tasks_moved"] == 2
