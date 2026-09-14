---
event_id: H-AFH-003
name: Agents for Humans Hackathon
platform: Devpost
status: committed
decision: commit
external_registration: confirmed
event_url: https://agentsforhumans.devpost.com
registration_url: https://agentsforhumans.devpost.com
worksheet_path: agents-for-humans/triage/worksheet.md
discovered_at: 2026-08-27
registration_deadline: null
start_at: 2026-08-10T23:00:00+07:00
submission_deadline: 2026-09-15T07:00:00+07:00
timezone: UTC+07:00
source_timezone: PDT
priority_1_5: 5
opportunity_1_5: 3
urgency_1_5: 5
strategic_fit_1_5: 3
p_ship: 0.60
p_win: 0.15
confidence: low
evidence_state: researched
constraint_load_1_5: 3
constraint_flags: [time, required_stack, access, overlap]
estimated_hours: 40
capacity_status: reserved
next_action: Ship Solomon's Genie Fleet Professional skeleton today (mocked matrix + Strands tool)
next_action_due: 2026-09-14
last_reviewed: 2026-09-14
source_links:
  - https://agentsforhumans.devpost.com
  - https://agentsforhumans.devpost.com/rules
  - https://agentsforhumans.devpost.com/details/dates
  - https://agentsforhumans.devpost.com/resources
notes: >-
  AI-owned scores provisional, last_reviewed 2026-09-14 UTC+07:00. Track locked
  to Professional Agents per user 2026-09-14. Project: Solomon's Genie Fleet —
  route/task optimizer, Functional Core mocked in Python (SoA arrays), C++
  pybind11 as stretch only. Published deadline Sep 14 17:00 PDT =
  2026-09-15T07:00:00+07:00. Strands Agents SDK required (Python/TS);
  AgentCore strengthens score but not required. AWS credits $50 via Resources
  form; credit-form URL conflict unresolved.
---

# Event Triage Worksheet — Agents for Humans (H-AFH-003)

> Standalone execution plane. Portfolio summary lives in root `TRIAGE.md`.
> Timezone: `UTC+07:00` storage/display; source `PDT` preserved.
> AI owns priority/opportunity/p_ship/p_win; human owns status/decision/fit/hours/capacity.

**Event:** Agents for Humans **Dates:** 2026-08-10 → 2026-09-15T07:00:00+07:00 **Format:** solo
**Total your-hours available:** 40 h
**Event link / rubric URL:** https://agentsforhumans.devpost.com/rules

---

## Stage 0 — Recon (target: T-7d or ASAP — compressed to T-0h, Sep 14)

### Judging criteria (from Devpost, retrieved 2026-09-14 via Exa)
| Published criterion | Weight if given | My answer plan |
|---|---|---|
| 1. Technical Implementation — how thoroughly/skillfully Strands used; genuine effort, working non-trivial implementation; live demo and/or AgentCore strengthens | — | Strands Python `@tool` for optimizer; mocked SoA core; live demo + diagram; AgentCore only if time |
| 2. Design — complete coherent product experience, not just proof of concept | — | Single operator flow: constraint input → optimized dispatch → decision surfacing |
| 3. Potential Impact — credible specific case for real audience, solution addresses problem per demo | — | Field-service dispatcher: sick-leave re-route with fuel minimization, before/after |
| 4. Creativity & Originality — creative non-obvious use, genuine problem understanding | — | DOD tradeoff pitch: SoA + zero-copy boundary, lightweight ghost footprint |

### Requirements screen (hard floor)
- [x] Eligibility (age/geo/affiliation) checked — open worldwide, solo ok [FACT]
- [x] Required tech/platform listed — Strands Agents SDK (Python/TS), AWS account/Builder ID [FACT]
- [x] Required APIs/sponsors tools identified: Strands SDK, Bedrock model, optional AgentCore
- [x] Submission artifacts required: video 5 min · public repo/license/diagram · text description · Built With includes Strands
- [x] Pre-existing code allowed? rules say: new or significantly updated after start; explain update

### Sponsor & prize map
| Sponsor | Prize/bounty | Fits my stack? | Category crowded? (L/M/H) |
|---|---|---|---|
| AWS / Strands — $40k across 3 tracks | Professional Agents track | Yes — Python Strands, Fargate/App Runner | M (5,355 participants total) |

### Saturation forecast (re-check at T-24h — now T-0h)
- Theme chatter: 5,355 participants; professional productivity crowded
- Near-identical builds? Generic copilots/chatbots flood; DOD/perf-angle optimizer is differentiated

### Pre-event prep
- [ ] Auth/deploy scaffold ready at: `agents-for-humans/` (Strands quickstart + AWS creds)
- [ ] Demo recording setup tested
- [ ] Stack frozen at **4–5 technologies**: 1 Python + Strands 2 PyArrow (mocked SoA) 3 AWS Fargate/App Runner 4 Bedrock model 5 YouTube demo

---

## Idea candidates

| # | Idea (one line) | Named user + pain | Demo path in ≤90s? | Fresh window? Why |
|---|---|---|---|---|
| 1 | Solomon's Genie Fleet — Professional route/task optimizer, mocked SoA matrix + Strands tool | Dispatcher re-routes sick-leave district in minutes, minimizes fuel | Yes: NL constraint → tool call → dispatch board before/after | Yes: perf-tradeoff angle vs generic copilots |
| 2 | Reconciliation agent (fallback) | Ops audit mismatch hunt | Yes, but IO-heavy for today | No — overlaps Idea 1 core |
| 3 | Local KB search (fallback) | Personal notes recall | Yes, but needs embeddings now | No — DB scope for today |

---

## Gate A — kill-gates

| Gate | Question | #1 |
|---|---|---|
| A1 Requirements fit | every rule/artifact satisfiable in my hours? | PASS — Strands Python, repo+diagram+5min video doable today |
| A2 Saturation | not clone-flooded? | PASS — optimizer + DOD pitch, not chatbot |
| A3 Solo feasibility | one demo path, ≤60% hours? | PASS — mocked matrix, 1 tool, 1 flow; C++ excluded today |
| A4 Window alive | edge not decayed? | PASS — deadline today, submit tonight |
| **Verdict** | | PASS → build |

**Killed & why:** #2/#3 fallback only, out of window today.
**Reshaped ideas:** #1 narrowed to heavily mocked matrix per user 2026-09-14.

---

## Gate B — HackScore matrix (compressed for T-0h)

| Criterion | Wt | Idea 1 |
|---|---|---|
| B1 Demo-path strength | 0.25 | 4 — one 90s path, mocked but survives failure |
| B2 Rubric coverage balance | 0.20 | 4 — Strands + design + impact + originality all answered |
| B3 Edge-window freshness | 0.20 | 4 — perf angle in crowded field |
| B4 Judge-consensus breadth | 0.15 | 3 — broadly liked, one skeptic on mock depth |
| B5 Impact & story shape | 0.10 | 4 — named dispatcher + before/after |
| B6 Feasibility margin | 0.10 | 4 — known stack, mock keeps buffer |
| **Weighted total** | 1.00 | 3.90 |
| Any criterion = 1? | — | No |

**CHOSEN IDEA:** #1 Solomon's Genie Fleet — Professional Agents
**Predicted HackScore:** 3.90

---

## Build plan (40h reserved, compressed to today)

| Block | % of hours | Hours | Output |
|---|---|---|---|
| Skeleton (end-to-end thinnest path) | first 25% | 10 | Strands agent + 1 mocked optimizer tool + CLI demo |
| Core features (max 2–3 must-haves) | 25→60% | 14 | Constraint parse → dispatch board → decision ping |
| Polish + submission artifacts | last 15%+slack | 16 | 5-min video, README, diagram, Devpost page |

Must-have features: 1 Strands `@tool` optimize_dispatch (mocked SoA) 2 Dispatcher UI/CLI before-after 3 Demo video + architecture diagram
Explicitly NOT building: C++ pybind11 native core, real vector DB, AgentCore deploy (stretch), multi-track entries

## Checkpoint tracker

| Clock | Checkpoint | Pass? | Notes |
|---|---|---|---|
| T+25% | Working skeleton runs end-to-end | ☐ | |
| T+40% | Mid-triage: re-score B1/B6 vs reality | ☐ | |
| T+60% | Feature freeze | ☐ | |
| T−8h | QA sweep started | ☐ | |
| T−4h | CODE LOCK — docs/copy only; backup video | ☐ | |
| T−2h | Rehearsed demo ×5, timed | ☐ | |
| T−30m | SUBMITTED | ☐ | |

AI-delegation log: ________________________________

---

## Submission QA

- [ ] Every required field filled; URLs public logged-out testable
- [ ] Strands listed under Built With
- [ ] Video ≤5min: problem → solution → demo → tech → close
- [ ] Backup video recorded & linked
- [ ] Description embeds images; markdown-formatted
- [ ] Honesty pass: mocked matrix stated plainly
- [ ] Submitted ≥30 min before deadline (target 2026-09-15T06:30:00+07:00)

---

## Post-mortem (within 48h)

| Log | Prediction | Actual | Lesson |
|---|---|---|---|
| Gate A near-misses | | | |
| Per-criterion score vs feedback | | | |
| Velocity felt vs measured | | | |
| Window verdict | | | |
| Placement / prizes | | | |
