# Demo Rehearsal Checklist

Source: `triage/worksheet.md` — Checkpoint tracker + Submission QA.
Deadline: **2026-09-15T07:00:00+07:00** — submit by **06:30** (≥30 min early).

## Rehearsal passes (×5, timed, target 4:40, hard cap 5:00)

- [ ] Pass 1 — cold read with script, note overruns per section
- [ ] Pass 2 — full CLI take (`mise run demo`), confirm verbatim output
- [ ] Pass 3 — CLI + API take (`:8002` curls), confirm `tasks_moved → 2`
- [ ] Pass 4 — failure drill: kill API, recover on CLI-only take
- [ ] Pass 5 — final timed take, no stops; record duration: ____

## Pre-record setup

- [ ] `lsof -i -P -n | grep LISTEN` — confirm `8002` free of sibling ports
      (`8001`/`8788` call-e, `8000` ATA, `3000`/`8787` WebMCP untouched)
- [ ] `mise run dev` booted (or `pitchfork start --all`), `/health` → `ok`
- [ ] Terminal font ≥18 pt, 1080p capture, `jq` installed
- [ ] Script open at `docs/video-script.md`; fallback `mise run demo` ready

## CODE LOCK reminder

- [ ] T−4h CODE LOCK: docs/copy only after lock — no source changes
- [ ] Only this slice's docs files change (`docs/video-script.md`,
      `docs/demo-rehearsal.md`); no new deps, no AWS, no ports beyond `8002`

## Submission QA (from worksheet)

- [ ] Every required field filled; URLs public, logged-out testable
- [ ] Strands listed under Built With
- [ ] Video ≤5 min: problem → solution → demo → tech → close
- [ ] Backup video recorded & linked
- [ ] Description embeds images; markdown-formatted
- [ ] Honesty pass: mocked matrix stated plainly
- [ ] Submitted ≥30 min before deadline (target 2026-09-15T06:30:00+07:00)

## Judging criteria → timestamp + evidence map

| # | Criterion (Devpost) | Video timestamp | Evidence shown on camera |
|---|---|---|---|
| 1 | Technical Implementation — Strands use, working non-trivial implementation | 3:20–4:10 (Tech) | `GET /ready` tool metadata (`optimize_dispatch`, `strands_available`), `path` field (`direct-tool` vs `strands-agent`), honesty line on mocked SoA core |
| 2 | Design — complete coherent product experience | 0:40–1:20 (Solution) | One operator flow (constraint → dispatch → board) + architecture diagram + before/after board |
| 3 | Potential Impact — credible case for a real audience | 0:00–0:40 (Problem) + 1:20–3:20 (Demo) | Dispatcher sick-leave story; Maya outage → 2/6 moved, fuel 12.7 → 22.43 (+9.73) before/after |
| 4 | Creativity & Originality — creative non-obvious use | 3:20–4:10 (Tech) | DOD tradeoff pitch: mocked SoA + zero-copy boundary, lightweight ghost footprint; deterministic replay-locked core |

## If blocked

- API will not boot → ship the CLI-only take (`mise run demo` covers the
  same core and all demo numbers).
- Video runs long → cut the API Plan B, never the honesty line.
- Any doubt about live/AWS → stay mock; live Bedrock/AgentCore is stretch
  and requires explicit human gating.
