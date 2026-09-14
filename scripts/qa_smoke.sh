#!/usr/bin/env bash
# Ephemeral QA smoke: starts the API, curls every endpoint, cleans up.
# Zero AWS spend (mock mode). Fails loudly on any non-200 or bad payload.
set -euo pipefail

API_PORT="${API_PORT:-8002}"
MODE="ephemeral"
if [[ "${1:-}" != "--ephemeral" ]]; then
  MODE="attached"
fi

pass() { echo "smoke: PASS $1"; }
fail() { echo "smoke: FAIL $1" >&2; exit 1; }

command -v jq >/dev/null || fail "jq is required but not installed"

check_endpoint() {
  local name="$1" url="$2" jq_filter="$3" expected="$4"
  local body http
  body="$(curl -sf "http://127.0.0.1:${url}")" || fail "$name unreachable ($url)"
  http="$(echo "$body" | jq -r "$jq_filter")" || fail "$name unparseable"
  [[ "$http" == "$expected" ]] || fail "$name expected [$expected] got [$http]"
  pass "$name"
}

if [[ "$MODE" == "ephemeral" ]]; then
  if curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    fail "port ${API_PORT} already serving before ephemeral start; aborting"
  fi
  GENIE_MODE=mock PYTHONPATH=src python -m uvicorn genie_fleet.api:create_app --factory \
    --host 127.0.0.1 --port "$API_PORT" >/tmp/genie-api-$$.log 2>&1 &
  API_PID=$!
  trap 'kill $API_PID 2>/dev/null || true; wait 2>/dev/null || true' EXIT
  for _ in $(seq 1 30); do
    curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

check_endpoint "api-health" "${API_PORT}/health" ".status" "ok"
check_endpoint "api-ready-mode" "${API_PORT}/ready" ".mode" "mock"
check_endpoint "api-ready-tool" "${API_PORT}/ready" ".tool.tool_name" "optimize_dispatch"

REQ_ID="$(curl -sI "http://127.0.0.1:${API_PORT}/health" | grep -i '^X-Request-Id:' | tr -d '\r' || true)"
[[ -n "$REQ_ID" ]] || fail "request-id header missing"
pass "request-id header"

DISPATCH="$(curl -sf -X POST "http://127.0.0.1:${API_PORT}/dispatch" \
  -H 'Content-Type: application/json' -d '{"absent_tech":"Maya"}')"
echo "$DISPATCH" | jq -e '.report.tasks_moved == 2' >/dev/null || fail "dispatch payload"
echo "$DISPATCH" | jq -e '.report.tasks_total == 6' >/dev/null || fail "dispatch totals"
pass "dispatch payload (Maya outage → 2 moved / 6 total)"

echo "smoke: all green (mode=$MODE, spend=\$0)"
