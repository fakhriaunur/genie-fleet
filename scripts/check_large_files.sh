#!/usr/bin/env bash
# Large file gate: source files stay reviewable (700 lines / 150KB).
set -euo pipefail
fail=0
while IFS= read -r f; do
  lines="$(wc -l < "$f")"
  bytes="$(wc -c < "$f")"
  if [[ "$lines" -gt 700 || "$bytes" -gt 153600 ]]; then
    echo "large-files: $f too big (${lines} lines, ${bytes} bytes)" >&2
    fail=1
  fi
done < <(find src scripts tests -name "*.py" -o -name "*.sh" | grep -v __pycache__)
[[ "$fail" == "0" ]] || exit 1
echo "large-files: all files within limits"
