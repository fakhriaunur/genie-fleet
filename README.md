# Genie-Fleet

Solomon's Genie Fleet — Professional route/task optimizer, mocked SoA matrix + Strands tool, Agents for Humans hackathon.

**Status: M1 foundation.** Mocked core (pure deterministic Python); Bedrock/AgentCore live run is stretch.

## Quickstart

```bash
mise install
mise run setup   # seeds .env only if missing; never overwrites
mise run qa      # ephemeral smoke: API up, curls every endpoint
mise run check   # lint + type + test
```

Manual equivalent: `cp .env.example .env` (leave `STRANDS_MODEL_ID` empty),
`pip install -e ".[dev]"`, then `mise run dev` (API on `:8002`).
Or `pitchfork start --all`, then `pitchfork logs api`.

## Endpoints

| Service | Endpoint | Meaning |
|---|---|---|
| API `:8002` | `GET /health` | `{"status":"ok"}` |
| API `:8002` | `GET /ready` | mock mode + `optimize_dispatch` metadata |
| API `:8002` | `POST /dispatch {"absent_tech":"Maya"}` | 2 moved / 6 total |
| API `:8002` | `GET /docs` | Swagger UI (schema committed at `docs/openapi.json`) |

Drive:

```bash
curl -s http://127.0.0.1:8002/health | jq
curl -s http://127.0.0.1:8002/ready | jq .mode
curl -s -X POST http://127.0.0.1:8002/dispatch \
  -H 'Content-Type: application/json' -d '{"absent_tech":"Maya"}' | jq .report.tasks_moved
```

Expected: `GET /health` → `{"status":"ok"}`, `GET /ready` → mock mode
report without any key, `POST /dispatch` → Maya outage moves 2 of 6 tasks.

## Demo (zero spend)

```bash
mise run demo     # sick-leave re-route dispatch board before/after
mise run preview  # JSON dispatch report against the canned scenario
```

Both run offline against the pure matrix core. Output is replay-locked via
`mise run replay` (golden fixtures in `tests/replay/`).

## Scenarios

```bash
pytest tests/scenarios -q
```

Happy/heavy/edge suites lock the outage contract:

| Absent | Moved / Total | Fuel before → after |
|---|---|---|
| Maya | 2 / 6 | 12.7 → 22.43 |
| Rio | 2 / 6 | 12.7 → 29.28 |
| Sam | 2 / 6 | 12.7 → 29.28 |

## CI

`.github/workflows/ci.yml` runs lint + type + test + replay on push/PR (Python 3.14).

## Mock vs live

- Default `GENIE_MODE=mock`: every automated flow (tests, QA smoke,
  replay, demo, preview) runs offline. Spend: $0.
- Live (stretch, human-gated): `GENIE_MODE=live` requires
  `STRANDS_MODEL_ID` plus AWS credentials; the app refuses to boot live
  without a model (fail-closed in `settings.py`).
- Live path resolves `STRANDS_MODEL_ID` via `BedrockModel` (`AWS_REGION`,
  default `ap-southeast-3`); missing model or bad credentials fail closed
  with an honest error, never silent mock. See `docs/rehearsal-log-m5.md`.

## Credentials

`.env` is gitignored. Copy `.env.example`; `STRANDS_MODEL_ID` and AWS creds
are needed only for gated live runs. Never commit `.env`, never print keys.

## License

MIT. See `LICENSE`.
