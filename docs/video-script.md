# Genie-Fleet — Video Script (≤5:00)

Track: Professional Agents. Mock-first; zero AWS spend on camera.
Total runtime: **4:40** (20 s buffer under the 5:00 cap).

On-camera commands (exact, from `mise.toml` + `README.md`):

```bash
mise run demo
curl -s http://127.0.0.1:8002/health | jq
curl -s http://127.0.0.1:8002/ready | jq .mode
curl -s -X POST http://127.0.0.1:8002/dispatch \
  -H 'Content-Type: application/json' -d '{"absent_tech":"Maya"}' | jq .report.tasks_moved
```

Verified outputs below were transcribed from real runs on 2026-09-14
(`mise run demo`, `mise run preview`, live API curls on `:8002`).

---

## 0:00–0:40 — Problem (0:40)

**On screen:** title card "Solomon's Genie Fleet — sick-leave re-route in minutes".

**Say:**

> Field-service dispatchers lose their morning when a tech calls in sick.
> One absence strands a whole district, and re-routing by hand burns fuel and
> misses SLAs. Genie-Fleet answers one question: with Maya out sick, who
> absorbs her district at minimum added fuel?

**Show:** nothing to run yet — title + one-line problem statement.

## 0:40–1:20 — Solution (0:40, cumulative 1:20)

**On screen:** `docs/architecture.md` request-flow diagram + endpoint table.

**Say:**

> A sick-leave report hits `POST /dispatch`, the agent shell parses the tech
> name, and the Strands `optimize_dispatch` tool re-routes the district
> through a pure deterministic matrix core with fuel accounting, returning a
> dispatch board. One operator flow: constraint input, optimized dispatch,
> decision surfacing.

**Show:** scroll the architecture diagram; highlight
`POST /dispatch → parse_absent_tech → optimize_dispatch → matrix core →
fuel accounting → dispatch board`.

## 1:20–3:20 — Live demo (2:00, cumulative 3:20)

**Run on camera (Plan A — CLI):**

```bash
mise run demo
```

**Expected on-screen output (verbatim):**

```text
genie-fleet demo [offline-core] (spend: $0)
absent: Maya (fuel 12.7 → 22.43, +9.73; 2/6 tasks moved)
  task 0: Maya → Rio (zone north, P5)
  task 1: Maya → Sam (zone north, P4)
path: direct-tool (offline; Bedrock/AgentCore is stretch)
```

**Say while it runs:**

> Maya is out. Two of six tasks move — task 0 to Rio, task 1 to Sam, both
> north zone — and added fuel is plus 9.73, from 12.7 to 22.43. Before-after
> board, deterministic every run.

**Run on camera (Plan B — API, same take if time allows):**

```bash
curl -s http://127.0.0.1:8002/health | jq
# → { "status": "ok" }
curl -s http://127.0.0.1:8002/ready | jq .mode
# → "mock"
curl -s -X POST http://127.0.0.1:8002/dispatch \
  -H 'Content-Type: application/json' -d '{"absent_tech":"Maya"}' | jq .report.tasks_moved
# → 2
```

**Full dispatch JSON (reference, `mise run preview` — key fields):**

```json
{
  "mode": "mocked",
  "absent_tech": "Maya",
  "fuel_before": 12.7,
  "fuel_after": 22.43,
  "added_fuel": 9.73,
  "tasks_moved": 2,
  "tasks_total": 6
}
```

**Fallback if the API will not boot on camera:** stay on the CLI take —
it exercises the same pure core and is replay-locked (`mise run replay`,
golden fixtures in `tests/replay/`).

## 3:20–4:10 — Tech (0:50, cumulative 4:10)

**On screen:** terminal showing `GET /ready` full body:

```json
{
  "mode": "mock",
  "version": "0.1.0",
  "tool": {
    "tool_name": "optimize_dispatch",
    "strands_available": false,
    "core": "mocked SoA arrays (plain Python; Arrow/C++ is stretch)"
  },
  "techs": ["Maya", "Rio", "Sam"]
}
```

**Say (honesty line — read verbatim):**

> Honesty pass: the matrix core is mocked SoA arrays in plain Python —
> deterministic, offline, zero spend. Strands integration is the real
> `optimize_dispatch` tool; the response `path` field records whether the
> `strands-agent` or `direct-tool` branch ran, so a mock is never presented
> as a model run. PyArrow, the C++ pybind11 core, Bedrock, and AgentCore are
> stretch, not in this take.

## 4:10–4:40 — Close (0:30, cumulative 4:40)

**Say:**

> Genie-Fleet: one sick-leave call in, minimum-fuel dispatch board out —
> Strands on the tool boundary, determinism in the core. Repo, diagram, and
> replay fixtures are public; Built With lists Strands. Thank you.

**On screen:** repo URL + Devpost link + "Built With: Strands Agents SDK".

---

### Recording notes

- Record at 1080p, terminal font ≥18 pt, `jq` output visible.
- Pre-boot the API (`mise run dev`, port `8002` only) before rolling; keep
  the `mise run demo` fallback one keystroke away.
- Strands/AgentCore stretch caveat stays in every cut — do not trim the
  honesty line to save time; trim the API Plan B instead.
