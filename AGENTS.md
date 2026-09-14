# Genie-Fleet Project Guide

## Mission

Genie-fleet is a mock-first dispatcher optimizer: a sick-leave report comes
in, the pure `matrix` core re-routes the absent tech's district with minimum
added fuel, and the `optimize_dispatch` Strands tool is the judged
integration. Demo and preview are always safe (zero AWS spend); a live
Bedrock/AgentCore run is stretch and requires explicit human gating. The
matrix is a pure deterministic core; Strands SDK calls are a thin imperative
shell.

## Repository layout

- `src/genie_fleet/`: application code (`api`, `settings`, `logging`,
  `matrix`, `agent`, `tools`, `cli`).
- `tests/`: unit, integration, and replay (committed golden fixtures).
- `scripts/`: `qa_smoke.sh`, `export_openapi.py`, `wheel_smoke.py`,
  `verify_wheel.sh`, repo contract checks.
- `triage/`: event worksheet and execution record.
- `docs/openapi.json`: committed FastAPI schema (`mise run export-openapi`).

## File editing

Use `Edit`/`Create` for changes; keep diffs reviewable and preserve user work.
Review each change before committing.

## Tooling contract

Use **mise** as project toolchain and task runner. Pin runtime and dependency
versions in project configuration; prefer `mise run <task>` over ad-hoc
commands. Do NOT set `min_version` in `mise.toml` — floors hard-fail older
runners; document floors instead. Mise Python is an isolated prefix (no venv
needed). Mise `[env]` `GENIE_MODE=mock` takes precedence; live runs happen
outside mise via explicit env.

Use **Pitchfork** as local service manager. Keep service definitions, health
checks, logs, and shutdown behavior explicit. Do not start persistent services
without user authorization (`pitchfork start` is the authorized path).

Packaging (M10, best-effort native hook): `mise run build-wheel` builds the
wheel into `dist/` (pure-Python default; `GENIE_NATIVE=1` embeds the
top-level `.so`); `mise run verify-wheel` proves flag-off, flag-on, and
editable no-toolchain installs in isolated prefixes. `GENIE_NATIVE` stays
off at runtime.

## Naming conventions (enforced by ruff pep8-naming)

- `snake_case` for functions, variables, parameters, and modules.
- `PascalCase` for classes and exception types.
- `UPPER_SNAKE_CASE` for module constants and canned fixtures.

## Required checks

Before commit, run the narrowest relevant `mise` tasks for formatting,
linting, type checking, and tests. Record failed or skipped checks.

```bash
mise run lint   # ruff format --check + ruff check
mise run type   # mypy strict on src/ + scripts/export_openapi.py
mise run test   # pytest with 35% coverage floor
mise run check  # lint + type + test
./scripts/qa_smoke.sh --ephemeral  # one-shot curl smoke, zero AWS spend
mise run replay  # golden-fixture replay
mise run tech-debt  # TODOs must reference an issue
mise run large-files  # 700 lines / 150KB per file
mise run agents_md  # AGENTS.md tasks/paths still match code
mise run devcontainer-verify  # devcontainer contract without docker
```

## Service Boundaries (NEVER VIOLATE)

- API: `8002` (FastAPI, `mise run dev` / `pitchfork logs api`). Health:
  `GET /health` → `{"status":"ok"}`. Ready: `GET /ready` → mode report
  (mock + `optimize_dispatch` tool metadata). Dispatch:
  `POST /dispatch {"absent_tech":"Maya"}` → 2 moved / 6 total.
- All automated QA uses mock mode (`GENIE_MODE=mock`); zero spend. There is
  no mock daemon — none exists; the API boots credential-free.
- Sibling ports on this shared host: call-e uses `8001`/`8788`, ATA uses
  `8000`, WebMCP uses `3000`/`8787` — never bind those here.
- Off-limits ports: `22`/`53`/`111`/`631`/`904`/`9000`/`3389`/`34115`/`33519`
  and `54620-54630` (Factory Droid MCP) — never bind or probe destructively.
- Always `lsof -i -P -n | grep LISTEN` before binding a new port.
- `STRANDS_MODEL_ID` and any AWS credentials never committed, never printed
  in logs or artifacts; `.env` is ignored.

## Authority and safety

- Mock-first is the authority: demo, preview, smoke, and replay run offline
  with no credentials. Live Bedrock requires explicit human approval.
- Never expose secrets, commit `.env`, or bypass the mock default.
- `docs/openapi.json` is regenerated via `mise run export-openapi` and
  committed; paths stay stable for review links.

## Agent operating model

One bounded capability for M1 (health + readiness), growing with the matrix:
**matrix core** (pure, deterministic) and **agent shell** (Strands I/O via
the `optimize_dispatch` tool, offline-first). Keep parsing, validation, and
re-routing deterministic. Human owns live-run approval, secret entry, push
approval, and Devpost submission.

## Interactive QA — Agent-Followable Path

No auth gate, no AWS key required — mock mode is the CI/QA contract:

**Deps & services (fresh clone to smoke):**
`mise install && mise run setup && mise run qa` — `mise run setup` is the
idempotent one-command setup (seeds `.env` only if missing, never overwrites).
Manual equivalent: `mise install` (Python 3.14.7, pitchfork 2.25.0),
`cp .env.example .env` (leave `STRANDS_MODEL_ID` empty),
`pip install -e ".[dev]"`.

**Launch:**

```bash
mise run dev    # uvicorn on 127.0.0.1:8002 (pitchfork logs api shows the same)
# or: pitchfork start --all, then pitchfork logs api
```

**Drive:**

```bash
curl -s http://127.0.0.1:8002/health | jq
curl -s http://127.0.0.1:8002/ready | jq .mode
curl -s -X POST http://127.0.0.1:8002/dispatch -H 'Content-Type: application/json' -d '{"absent_tech":"Maya"}' | jq .report.tasks_moved
./scripts/qa_smoke.sh --ephemeral  # full smoke, no manual cleanup
mise run replay  # golden-fixture replay
```

Expected: `GET /health` → `{"status":"ok"}`, `GET /ready` → mock mode report
without any key, `POST /dispatch` → Maya outage moves 2 of 6 tasks.

## Git workflow

Use conventional commits (`feat(scope):`, `fix(scope):`, `docs:`, `test:`,
`chore:`). Never commit secrets or generated credentials. Review staged diff
before committing. Do not push without explicit human authorization. Do not
rewrite published history.
