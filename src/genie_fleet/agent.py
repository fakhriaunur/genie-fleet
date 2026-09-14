"""Strands agent wrapper. Natural-language constraint → dispatch board.

Live path: a real Strands ``Agent`` carrying the ``optimize_dispatch`` tool
(Bedrock model). Offline path: the request is parsed for a tech name and the
tool is invoked directly, so the demo and QA never need credentials. The
response always states which path ran — no mock masquerading as a model.
"""

from __future__ import annotations

from typing import Any

from genie_fleet._native import try_native_optimize
from genie_fleet.logging import get_logger
from genie_fleet.matrix import CANNED_ABSENT_TECH, TECH_HOME, optimize_many
from genie_fleet.settings import Settings, load_settings
from genie_fleet.tools import STRANDS_AVAILABLE, optimize_dispatch

TECH_NAMES = tuple(sorted(TECH_HOME))

logger = get_logger("genie_fleet.agent")


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


def run_with_strands(text: str, settings: Settings | None = None) -> dict[str, Any]:
    """Run the request through a real Strands Agent. Raises on any failure.

    The Agent is built on the Bedrock provider path with the configured
    model id and region (``Settings.strands_model_id`` /
    ``Settings.aws_region``). Refuses fail-closed when no model id is
    configured; raises on any failure so callers can fall through honestly.
    """
    from strands import Agent  # lazy: keeps offline import light
    from strands.models import BedrockModel  # lazy: Bedrock provider path

    resolved = settings if settings is not None else load_settings()
    if not resolved.strands_model_id:
        raise RuntimeError(
            "live Strands dispatch requires STRANDS_MODEL_ID; "
            "refusing to construct the Agent without a model (fail-closed)."
        )

    provider = BedrockModel(
        model_id=resolved.strands_model_id,
        region_name=resolved.aws_region,
    )
    agent = Agent(model=provider, tools=[optimize_dispatch])
    absent = parse_absent_tech(text)
    result = agent(
        f"A dispatcher reports {absent} called in sick. "
        f"Re-route their district with minimum fuel: "
        f"call optimize_dispatch with absent_tech={absent}."
    )
    return {"path": "strands-agent", "result": str(result), "absent_tech": absent}


def _singular_report(
    absent: str, use_native_flag: bool
) -> tuple[dict[str, object], bool]:
    """Compute one single-outage report, natively when opted in.

    Returns ``(report, via_native)``. Tries ``try_native_optimize`` first
    so GENIE_NATIVE=1 with the extension present routes natively; any
    None falls back to the pure-Python ``optimize_dispatch`` tool.
    Multi-outage callers never use this (native is singular-only).
    """
    native_report = try_native_optimize(absent, use_native_flag)
    if native_report is not None:
        return native_report, True
    report = optimize_dispatch(absent)
    if not isinstance(report, dict):
        raise TypeError("optimize_dispatch must return a report dict")
    return report, False


def _offline_outcome(
    absent: str, use_native_flag: bool, live_failed: bool
) -> dict[str, Any]:
    """Build the offline outcome for one single-outage request."""
    report, via_native = _singular_report(absent, use_native_flag)
    if live_failed:
        return {
            "path": "live-error → direct-tool (offline fallback "
            "after live failure; Bedrock/AgentCore is stretch)",
            "absent_tech": absent,
            "report": report,
            "board": board_lines(report),
        }
    if via_native:
        return {
            "path": "direct-tool (native; SoA lists via genie_fleet_native)",
            "absent_tech": absent,
            "report": report,
            "board": board_lines(report),
        }
    return {
        "path": "direct-tool (offline; Bedrock/AgentCore is stretch)",
        "absent_tech": absent,
        "report": report,
        "board": board_lines(report),
    }


def run_dispatch_request(text: str, settings: Settings | None = None) -> dict[str, Any]:
    """Handle one dispatcher request; always returns board + report.

    The live Strands Agent is attempted only when ``settings.is_live`` is
    true AND the Strands SDK imports; a ``None`` settings (plain unit use)
    means mock, so mock mode always takes the direct-tool offline path even
    when the SDK is importable. A failed live attempt is logged distinctly
    and falls through to the deterministic offline path with an honest
    ``path`` label naming the live failure (never a bare direct-tool
    label, never masquerading as a model call).

    The offline report routes natively when ``settings.use_native`` opts
    in and the extension is present (byte-equal to Python); otherwise it
    falls back to the pure-Python tool. Multi-outage stays Python.
    """
    absent = parse_absent_tech(text)
    use_native_flag = settings.use_native if settings is not None else False
    live_attempted = settings is not None and settings.is_live and STRANDS_AVAILABLE
    live_failed = False
    if live_attempted:
        try:
            live = run_with_strands(text, settings)
            report, _ = _singular_report(absent, use_native_flag)
            live["report"] = report
            live["board"] = board_lines(report)
            return live
        except Exception as exc:
            logger.warning(
                "live Strands dispatch failed; "
                "falling back to direct-tool offline path: %s",
                exc,
            )
            live_failed = True
    return _offline_outcome(absent, use_native_flag, live_failed)


def run_multi_dispatch_request(
    absent_techs: list[str], settings: Settings | None = None
) -> dict[str, Any]:
    """Handle one multi-outage dispatcher request; returns board + report.

    Additive extension over the singular path: re-routes the union of the
    absent districts by composing the pure core primitives via
    ``optimize_many``. Honors the same ``is_live`` AND ``STRANDS_AVAILABLE``
    gate as ``run_dispatch_request`` — mock mode stays on the direct-tool
    offline path, while a live attempt that fails falls through honestly
    with a ``live-error`` path label. Raises ValueError for unknown techs
    or a full-crew outage so the API shell can answer with the established
    error body.
    """
    label = "+".join(sorted(set(absent_techs)))
    live_attempted = settings is not None and settings.is_live and STRANDS_AVAILABLE
    live_failed = False
    if live_attempted:
        try:
            live = run_with_strands(
                f"{label} called in sick. Re-route their districts with minimum fuel.",
                settings,
            )
        except Exception as exc:
            logger.warning(
                "live Strands multi-dispatch failed; "
                "falling back to direct-tool offline path: %s",
                exc,
            )
            live_failed = True
        else:
            report = optimize_many(absent_techs)
            live["absent_tech"] = label
            live["report"] = report
            live["board"] = board_lines(report)
            return live
    report = optimize_many(absent_techs)
    if live_failed:
        return {
            "path": "live-error → direct-tool (offline fallback "
            "after live failure; Bedrock/AgentCore is stretch)",
            "absent_tech": label,
            "report": report,
            "board": board_lines(report),
        }
    return {
        "path": "direct-tool (offline; Bedrock/AgentCore is stretch)",
        "absent_tech": label,
        "report": report,
        "board": board_lines(report),
    }
