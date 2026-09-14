"""Operator CLI. `demo` and `preview` are always safe (zero AWS spend)."""

from __future__ import annotations

import argparse
import json

from genie_fleet.agent import board_lines, run_dispatch_request
from genie_fleet.matrix import CANNED_ABSENT_TECH, TECH_HOME
from genie_fleet.tools import STRANDS_AVAILABLE


def build_parser() -> argparse.ArgumentParser:
    """CLI argument parser (kept separate for testability)."""
    parser = argparse.ArgumentParser(prog="genie-fleet")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="sick-leave dispatch board before/after")
    demo.add_argument("--absent", default=CANNED_ABSENT_TECH, help="sick tech name")
    preview = sub.add_parser("preview", help="JSON dispatch report, zero spend")
    preview.add_argument("--absent", default=CANNED_ABSENT_TECH, help="sick tech name")
    return parser


def cmd_demo(absent: str) -> int:
    """Print the before/after dispatch board. Never touches the network."""
    if absent not in TECH_HOME:
        print(f"unknown tech: {absent!r} (known: {sorted(TECH_HOME)})")
        return 2
    outcome = run_dispatch_request(f"{absent} called in sick")
    report = outcome["report"]
    if not isinstance(report, dict):
        raise TypeError("dispatch report must be a dict")
    sdk = "strands-sdk" if STRANDS_AVAILABLE else "offline-core"
    print(f"genie-fleet demo [{sdk}] (spend: $0)")
    for line in board_lines(report):
        print(line)
    print(f"path: {outcome['path']}")
    return 0


def cmd_preview(absent: str) -> int:
    """Print the JSON dispatch report. Never touches the network."""
    if absent not in TECH_HOME:
        print(f"unknown tech: {absent!r} (known: {sorted(TECH_HOME)})")
        return 2
    outcome = run_dispatch_request(f"{absent} called in sick")
    print(json.dumps(outcome["report"], indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint; returns process exit code."""
    args = build_parser().parse_args(argv)
    absent = str(args.absent)
    if args.command == "demo":
        return cmd_demo(absent)
    if args.command == "preview":
        return cmd_preview(absent)
    raise AssertionError(f"unknown command: {args.command}")  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
