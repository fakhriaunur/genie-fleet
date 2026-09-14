---
name: Bug report
about: Report a reproducible bug in genie-fleet (API, matrix core, or optimize_dispatch tool)
title: "fix: "
labels: [bug]
assignees: []
---

## Description

<!-- A clear, concise description of the bug. -->

## Reproduction

**Steps to reproduce**

1. Environment: `mise install` + `cp .env.example .env` (`STRANDS_MODEL_ID` empty for mock) + `pip install -e ".[dev]"`
2. Start: `mise run dev` (FastAPI on `127.0.0.1:8002`)
3. Action: `curl -s ...` or `python -m genie_fleet.cli preview`
4. Observed: <!-- what happened -->

**Expected**

<!-- what should happen per the matrix contract (Maya outage moves 2 of 6 tasks) -->

## Evidence

- `GET /health` → `curl -s http://127.0.0.1:8002/health`
- `GET /ready` → `curl -s http://127.0.0.1:8002/ready | jq .mode`
- `POST /dispatch` → `curl -s -X POST http://127.0.0.1:8002/dispatch -H 'Content-Type: application/json' -d '{"absent_tech":"Maya"}'`
- Logs: `pitchfork logs api`
- `mise run check` / `mise run replay` results

## Environment

- Python `python --version` → `3.14.7` (mise)
- `mise run` versions: <!-- paste `mise --version`, `ruff --version`, `mypy --version`, `pytest --version` -->
- `GENIE_MODE`: `mock` (never paste AWS keys or `STRANDS_MODEL_ID`)
- OS:

## Checklist

- [ ] No secrets pasted (`.env` gitignored, gitleaks safe)
- [ ] `mise run lint && mise run type` green
- [ ] Mock-first preserved (no credentials required to reproduce)
