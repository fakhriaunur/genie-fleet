"""Heavy-traffic dispatch scenarios (shells only, mock mode, $0 spend).

Covers the heavy leg of the scenario matrix: a 500-char notes dispatch
keeps the exact Maya 2/6 shape, and 20 concurrent Maya dispatches all
return HTTP 200 with tasks_moved 2, zero 5xx, and identical bodies.

Shells only: FastAPI TestClient in threads (no sockets, no credentials,
no port claims). The concurrent run is pure in-memory compute, so it
finishes in well under a second and the default suite stays fast with no
slow marker or quarantine needed. Does not touch the pure core,
TECH_HOME, the report shape, or replay goldens.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from genie_fleet.api import create_app
from genie_fleet.settings import Settings

app = create_app(Settings(mode="mock"))

# Exactly 500 chars (the API notes cap). Worded to contain no tech-name
# substrings, since parse_absent_tech matches case-insensitively and would
# otherwise resolve to the wrong tech; the test guards this explicitly.
NOTES_500 = ("Sick cover needed urgently, please reassign district. " * 10)[:500]


def test_maya_dispatch_with_500char_notes_keeps_exact_shape() -> None:
    assert len(NOTES_500) == 500
    lowered = NOTES_500.lower()
    assert "maya" not in lowered
    assert "rio" not in lowered
    assert "sam" not in lowered

    response = TestClient(app).post(
        "/dispatch", json={"absent_tech": "Maya", "notes": NOTES_500}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["absent_tech"] == "Maya"
    report = body["report"]
    assert report["tasks_moved"] == 2
    assert report["tasks_total"] == 6
    assert report["fuel_before"] == 12.7
    assert report["fuel_after"] == 22.43
    assert report["added_fuel"] == 9.73
    board = body["board"]
    assert len(board) == 3  # header + 2 moved-task lines
    assert "absent: Maya" in board[0]

    baseline = TestClient(app).post("/dispatch", json={"absent_tech": "Maya"})
    assert baseline.status_code == 200
    assert body["report"] == baseline.json()["report"]
    assert body["board"] == baseline.json()["board"]


def _post_maya_dispatch(_index: int) -> tuple[int, dict[str, object]]:
    with TestClient(app) as dispatch_client:
        response = dispatch_client.post("/dispatch", json={"absent_tech": "Maya"})
        return response.status_code, response.json()


def test_20_concurrent_maya_dispatches_all_succeed_identically() -> None:
    baseline = TestClient(app).post("/dispatch", json={"absent_tech": "Maya"})
    assert baseline.status_code == 200
    baseline_body = baseline.json()

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(_post_maya_dispatch, range(20)))

    assert len(results) == 20
    statuses = [status for status, _ in results]
    assert all(status == 200 for status in statuses)
    assert not any(status >= 500 for status in statuses)

    bodies = [body for _, body in results]
    for body in bodies:
        assert body["report"]["tasks_moved"] == 2
    first_body = bodies[0]
    assert all(body == first_body for body in bodies)
    assert first_body == baseline_body
