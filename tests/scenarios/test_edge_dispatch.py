"""Edge-case dispatch scenarios (shells only, mock mode, $0 spend).

Documents the accepted edge behavior of the dispatch shell without changing
it: an unknown tech returns HTTP 200 with an error body listing the known
techs (known quirk, asserted not fixed), an empty ``absent_tech`` is
rejected with 422 by request validation, whitespace-only input falls into
the unknown-tech error path, and free-text sick-leave variants resolve to
the right tech through ``run_dispatch_request``.

Shells only: FastAPI TestClient (no sockets, no credentials). Does not
touch the pure core, TECH_HOME, the report shape, or replay goldens.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from genie_fleet.agent import parse_absent_tech, run_dispatch_request
from genie_fleet.api import create_app
from genie_fleet.settings import Settings

client = TestClient(create_app(Settings(mode="mock")))
MOCK_SETTINGS = Settings(mode="mock")


def test_unknown_tech_returns_200_error_body_listing_known_techs() -> None:
    # Known quirk (pre-submission freeze): unknown techs get HTTP 200 with
    # an error body, not a 4xx. This test pins the quirk; it must not be
    # "fixed" without a new feature plus golden regen.
    response = client.post("/dispatch", json={"absent_tech": "Zed"})
    assert response.status_code == 200
    body = response.json()
    assert "Zed" in body["error"]
    assert body["known_techs"] == ["Maya", "Rio", "Sam"]
    assert "report" not in body


def test_empty_absent_tech_returns_422() -> None:
    response = client.post("/dispatch", json={"absent_tech": ""})
    assert response.status_code == 422


def test_whitespace_absent_tech_falls_into_unknown_tech_path() -> None:
    # Whitespace-only input passes request validation (min_length=1) but
    # matches no known tech, so it takes the same 200-with-error path as
    # any unknown tech instead of erroring the server.
    for absent in (" ", "   "):
        response = client.post("/dispatch", json={"absent_tech": absent})
        assert response.status_code == 200
        body = response.json()
        assert "error" in body
        assert body["known_techs"] == ["Maya", "Rio", "Sam"]
        assert "report" not in body


def test_parse_variants_resolve_to_the_right_tech() -> None:
    assert parse_absent_tech("Rio called in sick") == "Rio"
    assert parse_absent_tech("sam is out") == "Sam"
    # No tech name present: falls back to the canned Maya default.
    assert parse_absent_tech("someone is sick") == "Maya"
    assert parse_absent_tech("   ") == "Maya"


def test_dispatch_request_variants_resolve_end_to_end() -> None:
    expected = {
        "Rio called in sick": ("Rio", 29.28, 16.59),
        "sam is out": ("Sam", 29.28, 16.59),
        "someone is sick": ("Maya", 22.43, 9.73),
    }
    for text, (tech, fuel_after, added_fuel) in expected.items():
        outcome = run_dispatch_request(text, settings=MOCK_SETTINGS)
        assert outcome["absent_tech"] == tech
        assert outcome["path"].startswith("direct-tool")
        report = outcome["report"]
        assert isinstance(report, dict)
        assert report["tasks_moved"] == 2
        assert report["tasks_total"] == 6
        assert report["fuel_after"] == fuel_after
        assert report["added_fuel"] == added_fuel
