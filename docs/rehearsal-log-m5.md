# Rehearsal Log — M5 Submission

Date (UTC): 2026-09-14T17:06:19Z
Tree: `1e848ebbcb24b3bdcc2b04d89de569118cce16f3` (mock mode, `GENIE_MODE=mock`, zero spend)
API: `127.0.0.1:8002`, factory boot
(`python -m uvicorn genie_fleet.api:create_app --factory --host 127.0.0.1 --port 8002`)

All outputs below are quoted byte-exact as produced. Cross-check against
`docs/video-script.md`: **NO MISMATCH** — every script-quoted value
(fuel `12.7 → 22.43`, `2 moved / 6 total`, direct-tool path) equals live output.
The script was not edited.

## 1. `mise run demo` (exit 0, 281 bytes)

```text
[demo] $ python -m genie_fleet.cli demo
genie-fleet demo [offline-core] (spend: $0)
absent: Maya (fuel 12.7 → 22.43, +9.73; 2/6 tasks moved)
  task 0: Maya → Rio (zone north, P5)
  task 1: Maya → Sam (zone north, P4)
path: direct-tool (offline; Bedrock/AgentCore is stretch)
```

Script expects exactly this block (minus the `[demo] $ ...` mise echo line,
which is the task-runner prefix, not program output): match.

## 2. `mise run preview` (exit 0, 1220 bytes)

```text
[preview] $ python -m genie_fleet.cli preview
{
  "mode": "mocked",
  "absent_tech": "Maya",
  "fuel_before": 12.7,
  "fuel_after": 22.43,
  "added_fuel": 9.73,
  "tasks_moved": 2,
  "tasks_total": 6,
  "moved": [
    {
      "task_id": 0,
      "from": "Maya",
      "to": "Rio",
      "zone": "north",
      "priority": 5
    },
    {
      "task_id": 1,
      "from": "Maya",
      "to": "Sam",
      "zone": "north",
      "priority": 4
    }
  ],
  "board": [
    {
      "task_id": 0,
      "tech": "Rio",
      "status": "reassigned",
      "zone": "north",
      "priority": 5
    },
    {
      "task_id": 1,
      "tech": "Sam",
      "status": "reassigned",
      "zone": "north",
      "priority": 4
    },
    {
      "task_id": 2,
      "tech": "Rio",
      "status": "assigned",
      "zone": "east",
      "priority": 3
    },
    {
      "task_id": 3,
      "tech": "Rio",
      "status": "assigned",
      "zone": "east",
      "priority": 4
    },
    {
      "task_id": 4,
      "tech": "Sam",
      "status": "assigned",
      "zone": "west",
      "priority": 5
    },
    {
      "task_id": 5,
      "tech": "Sam",
      "status": "assigned",
      "zone": "west",
      "priority": 2
    }
  ]
}
```

Script key-field block (`mode`, `absent_tech`, fuel, moved/total): match.

## 3. `POST /dispatch {"absent_tech":"Maya"}` (HTTP 200, raw body, 978 bytes)

```json
{"path":"direct-tool (offline; Bedrock/AgentCore is stretch)","absent_tech":"Maya","report":{"mode":"mocked","absent_tech":"Maya","fuel_before":12.7,"fuel_after":22.43,"added_fuel":9.73,"tasks_moved":2,"tasks_total":6,"moved":[{"task_id":0,"from":"Maya","to":"Rio","zone":"north","priority":5},{"task_id":1,"from":"Maya","to":"Sam","zone":"north","priority":4}],"board":[{"task_id":0,"tech":"Rio","status":"reassigned","zone":"north","priority":5},{"task_id":1,"tech":"Sam","status":"reassigned","zone":"north","priority":4},{"task_id":2,"tech":"Rio","status":"assigned","zone":"east","priority":3},{"task_id":3,"tech":"Rio","status":"assigned","zone":"east","priority":4},{"task_id":4,"tech":"Sam","status":"assigned","zone":"west","priority":5},{"task_id":5,"tech":"Sam","status":"assigned","zone":"west","priority":2}]},"board":["absent: Maya (fuel 12.7 → 22.43, +9.73; 2/6 tasks moved)","  task 0: Maya → Rio (zone north, P5)","  task 1: Maya → Sam (zone north, P4)"]}
```

Key fields: `fuel_before 12.7`, `fuel_after 22.43`, `added_fuel 9.73`,
`tasks_moved 2`, `tasks_total 6`, `path` starts with `direct-tool`. Match.

Supporting calls on the same boot:

```text
GET /health → {"status":"ok"}
GET /ready  → {"mode":"mock","version":"0.1.0","tool":{"tool_name":"optimize_dispatch","strands_available":false,"core":"mocked SoA arrays (plain Python; Arrow/C++ is stretch)"},"techs":["Maya","Rio","Sam"]}
POST /dispatch → tasks_moved 2 (via jq .report.tasks_moved)
X-Request-Id present and unique per response on /health and /dispatch.
```

## 4. Cross-check vs `docs/video-script.md`

| Script-quoted value | Live output | Verdict |
|---|---|---|
| demo block (fuel 12.7 → 22.43, +9.73; 2/6; task 0→Rio P5; task 1→Sam P4; direct-tool path) | §1 | match |
| preview key fields (mocked/Maya/12.7/22.43/9.73/2/6) | §2 | match |
| health `{"status":"ok"}` | §3 | match |
| ready `.mode` → `"mock"` | §3 | match |
| dispatch `.report.tasks_moved` → `2` | §3 | match |
| ready full body (tool metadata, techs) | §3 | match |

**Result: no mismatch. Script left untouched.**

## 5. Public surface (verified logged-out, no credentials)

```text
git ls-remote origin HEAD → 49ca50dd3ee2c39787b752962c16aa5296a5aa21 (exit 0)
LICENSE → HTTP 200 (raw.githubusercontent.com, logged-out)
README.md → HTTP 200 (raw.githubusercontent.com, logged-out)
docs/openapi.json → HTTP 200 (raw.githubusercontent.com, logged-out)
```

Note: local tree is ahead of `origin/main` (unpushed submission work held
locally per no-push-without-approval policy); remote files verified at the
published `origin/main` revision. This log is committed locally, NOT pushed —
push awaits explicit human approval.
