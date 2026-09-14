---
name: Feature request
about: Propose an enhancement to genie-fleet (matrix core, agent shell, or QA)
title: "feat: "
labels: [enhancement]
assignees: []
---

## Problem

<!-- What user need or gap motivates this? -->

## Proposal

<!-- What should change? Keep the matrix core pure/deterministic; Strands I/O stays in the thin shell. -->

## Acceptance criteria

- [ ] <!-- observable, testable outcome 1 -->
- [ ] <!-- observable, testable outcome 2 -->
- [ ] `mise run check` green, `mise run replay` green (goldens updated only with justification)
- [ ] Mock-first preserved: demo/preview/smoke run with zero AWS spend

## Environment

- Python `python --version` → `3.14.7` (mise)
- `mise run` versions: <!-- paste `mise --version`, `ruff --version`, `mypy --version`, `pytest --version` -->
- `GENIE_MODE`: `mock`

## Notes

<!-- Links to triage worksheet, ADRs, or related issues. Out of scope: live Bedrock runs without explicit human approval. -->
