<!--
genie-fleet PR template — Conventional Commits + mock-first contract.
See AGENTS.md and triage/ for the QA path.
-->

## Description

<!-- What changed and why (1-3 sentences). Link issue: Closes # -->

## Type

<!-- conventional commits prefix: feat | fix | docs | test | chore | refactor -->

- [ ] `feat:` — new capability (matrix stays pure/deterministic; Strands I/O in thin shell only)
- [ ] `fix:` — bug fix (include reproduction + `mise run replay` pass)
- [ ] `docs:` — docs only (`docs/`, `README`, `AGENTS.md`, `triage/`)
- [ ] `test:` / `chore:` / `refactor:` — task-appropriate prefix

## Testing done

```bash
mise run check    # ruff format --check + ruff check + mypy strict + pytest (35% floor)
mise run replay   # golden-fixture replay
mise run qa       # ./scripts/qa_smoke.sh --ephemeral → health/ready/dispatch on :8002
```

- [ ] `mise run check` green — paste result:
- [ ] `mise run replay` green — paste result:
- [ ] `mise run qa` green (`GET /health` → `{"status":"ok"}`, `POST /dispatch` → 2 moved / 6 total) — paste result:
- [ ] `pre-commit run --all-files` green (if hooks installed)

## Checklist

- [ ] No secrets committed (`.env` gitignored, `STRANDS_MODEL_ID` and AWS keys never printed in logs/artifacts)
- [ ] `mise run replay` green (goldens unchanged, or diff justified)
- [ ] Submission path unchanged (`docs/openapi.json` regenerated via `mise run export-openapi` if API changed)
- [ ] No history rewrite / force-push (use `git revert` to roll back)
- [ ] `pyproject.toml` stays canonical (dependency changes only via `pyproject.toml` + refreshed `requirements.txt`)
