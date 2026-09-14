#!/usr/bin/env bash
# Validate that every `mise run <task>` referenced in AGENTS.md exists.
set -euo pipefail
missing=0
while read -r task; do
  if ! mise tasks ls 2>/dev/null | awk '{print $1}' | grep -qx "$task"; then
    echo "agents_md: task referenced but missing: mise run $task" >&2
    missing=1
  fi
done < <(grep -oE 'mise run [a-z_:.-]+' AGENTS.md | awk '{print $3}' | sort -u)
[[ "$missing" == "0" ]] || exit 1
echo "agents_md: all referenced tasks exist"

# Every `pitchfork <name>` word must match a [daemons.<name>] section.
missing_daemon=0
while read -r name; do
  if ! grep -qx "\[daemons\.${name}\]" pitchfork.toml; then
    echo "agents_md: pitchfork daemon referenced but missing: $name" >&2
    missing_daemon=1
  fi
done < <(grep -oE 'pitchfork [a-z_:.-]+' AGENTS.md | awk '{print $2}' | sort -u | grep -vx -e start -e stop -e logs || true)
[[ "$missing_daemon" == "0" ]] || exit 1
echo "agents_md: all referenced pitchfork daemons exist"
