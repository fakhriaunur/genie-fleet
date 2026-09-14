"""Strands agent wrapper. Natural-language constraint → dispatch board.

Live path: a real Strands ``Agent`` carrying the ``optimize_dispatch`` tool
(Bedrock model). Offline path: the request is parsed for a tech name and the
tool is invoked directly, so the demo and QA never need credentials. The
response always states which path ran — no mock masquerading as a model.
"""

from __future__ import annotations

from typing import Any

from genie_fleet.matrix import CANNED_ABSENT_TECH, TECH_HOME
from genie_fleet.tools import STRANDS_AVAILABLE, optimize_dispatch

TECH_NAMES = tuple(sorted(TECH_HOME))


def parse_absent_tech(text: str) -> str:
    """Extract a tech name from free text; default to the canned scenario."""
    lowered = text.lower()
    for name in TECH_NAMES:
        if name.lower() in lowered:
            return name
    return CANNED_ABSENT_TECH


def board_lines(report: dict[str, object]) -> list[str]:
    """Human-readable dispatch board lines from a dispatch report."""
    lines = [
        f"absent: {report['absent_tech']} "
        f"(fuel {report['fuel_before']} → {report['fuel_after']}, "
        f"+{report['added_fuel']}; "
        f"{report['tasks_moved']}/{report['tasks_total']} tasks moved)"
    ]
    moved = report.get("moved")
    if isinstance(moved, list):
        for entry in moved:
            if isinstance(entry, dict):
                lines.append(
                    f"  task {entry['task_id']}: "
                    f"{entry['from']} → {entry['to']} "
                    f"(zone {entry['zone']}, P{entry['priority']})"
                )
    return lines


def run_with_strands(text: str) -> dict[str, Any]:
    """Run the request through a real Strands Agent. Raises on any failure."""
    from strands import Agent  # lazy: keeps offline import light

    agent = Agent(tools=[optimize_dispatch])
    absent = parse_absent_tech(text)
    result = agent(
        f"A dispatcher reports {absent} called in sick. "
        f"Re-route their district with minimum fuel: "
        f"call optimize_dispatch with absent_tech={absent}."
    )
    return {"path": "strands-agent", "result": str(result), "absent_tech": absent}


def run_dispatch_request(text: str) -> dict[str, Any]:
    """Handle one dispatcher request; always returns board + report.

    Tries the live Strands Agent first when the SDK is importable; falls
    back to direct tool invocation otherwise. The ``path`` field records
    which branch ran.
    """
    absent = parse_absent_tech(text)
    if STRANDS_AVAILABLE:
        try:
            live = run_with_strands(text)
            report = optimize_dispatch(absent)
            if not isinstance(report, dict):
                raise TypeError("optimize_dispatch must return a report dict")
            live["report"] = report
            live["board"] = board_lines(report)
            return live
        except Exception:
            pass  # fall through to the deterministic offline path
    report = optimize_dispatch(absent)
    if not isinstance(report, dict):
        raise TypeError("optimize_dispatch must return a report dict")
    return {
        "path": "direct-tool (offline; Bedrock/AgentCore is stretch)",
        "absent_tech": absent,
        "report": report,
        "board": board_lines(report),
    }
