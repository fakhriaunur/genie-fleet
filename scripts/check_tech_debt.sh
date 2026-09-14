#!/usr/bin/env bash
# Tech debt gate: TODOs must reference an issue (TODO(#123)) or ticket.
set -euo pipefail
hits="$(grep -rn "TODO" --include="*.py" src/ scripts/ tests/ 2>/dev/null | grep -v "TODO(#" | grep -v "TODO(TICKET" || true)"
if [[ -n "$hits" ]]; then
  echo "tech-debt: untracked TODO found — use TODO(#123) or TODO(TICKET-123)" >&2
  echo "$hits" >&2
  exit 1
fi
echo "tech-debt: no untracked TODOs"
