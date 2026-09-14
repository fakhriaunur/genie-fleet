#!/usr/bin/env bash
# M10 packaged-wheel end-to-end proof (approach B, user-approved).
#
#   ./scripts/verify_wheel.sh build   # wheel into dist/ (honors GENIE_NATIVE)
#   ./scripts/verify_wheel.sh verify  # full matrix, all in scratch dirs:
#     flag-off: build (GENIE_NATIVE unset) -> no .so -> clean-prefix install
#       -> NATIVE_AVAILABLE False, golden byte-identical, Maya 2/6 smoke,
#       real replay suite green against the installed wheel
#     flag-on: GENIE_NATIVE=1 build -> top-level .so -> clean-prefix install
#       -> GENIE_NATIVE=1 native reports byte-equal, replay suite green
#     editable: pip install -e . with no toolchain on PATH still succeeds
#       and smokes green
#
# Nothing is ever installed into the repo env and nothing is written into
# the repo tree (except dist/ for the `build` subcommand, which is
# gitignored); `verify` fails if the working tree changes at all.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SMOKE="$REPO_ROOT/scripts/wheel_smoke.py"
WORK="$(mktemp -d /tmp/genie-verify-wheel.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

# The repo env exports PYTHONPATH=src (mise [env]); installed prefixes must
# never see the repo checkout or every "installed wheel" check is a lie.
unset PYTHONPATH

phase() { echo "verify-wheel: === $1 ==="; }
fail() {
  echo "verify-wheel: FAIL $1" >&2
  exit 1
}

make_prefix() {
  # $1 = dest dir. ensurepip is bundled; the upgrade needs PyPI once.
  python -m venv "$1"
  "$1/bin/pip" install --quiet --upgrade pip
}

real_tool_path() {
  # Bin dirs of the mise-pinned cmake+ninja plus the repo python, resolved
  # from the (trusted) repo checkout. Flag-on builds prepend these so the
  # hook probes the identical toolchain the e2e suite uses.
  local tool resolved
  for tool in cmake ninja python; do
    resolved="$(mise which "$tool" 2>/dev/null | tail -1 || true)"
    if [[ -n "$resolved" ]]; then
      dirname "$resolved"
    fi
  done | awk '!seen[$0]++' | paste -sd:
}

build_wheel() {
  # $1 = build python, $2 = outdir, $3 = flag "0"|"1". Prints the wheel path.
  local build_py="$1" outdir="$2" flag="$3" log="$WORK/build-$3.log"
  if [[ "$flag" == "1" ]]; then
    (cd "$REPO_ROOT" && env GENIE_NATIVE=1 PATH="$(real_tool_path):$PATH" \
      "$build_py" -m build --wheel --outdir "$outdir" .) >"$log" 2>&1 \
      || {
        tail -30 "$log" >&2
        fail "flag-on wheel build failed"
      }
  else
    (cd "$REPO_ROOT" && env -u GENIE_NATIVE \
      "$build_py" -m build --wheel --outdir "$outdir" .) >"$log" 2>&1 \
      || {
        tail -30 "$log" >&2
        fail "flag-off wheel build failed"
      }
  fi
  local wheel
  wheel="$(ls -t "$outdir"/*.whl 2>/dev/null | head -1 || true)"
  [[ -n "$wheel" ]] || fail "no wheel produced in $outdir (see $log)"
  echo "$wheel"
}

prefix_replay() {
  # $1 = prefix python, $2.. = extra env assignments. Runs the real replay
  # suite against the INSTALLED wheel: cwd is the scratch dir and the repo
  # ini (which injects src/) is bypassed, so repo sources cannot shadow.
  local prefix_py="$1"
  shift
  (cd "$WORK" && env GENIE_MODE=mock "$@" "$prefix_py" -m pytest \
    "$REPO_ROOT/tests/replay" -v -c /dev/null -p no:cacheprovider)
}

prefix_smoke() {
  # $1 = prefix python, $2 = --expect-pure|--expect-native, $3.. = env.
  local prefix_py="$1" expectation="$2"
  shift 2
  (cd "$WORK" && env GENIE_MODE=mock "$@" "$prefix_py" "$SMOKE" "$expectation")
}

cmd_build() {
  make_prefix "$WORK/tools-venv"
  local build_py="$WORK/tools-venv/bin/python"
  "$build_py" -m pip install --quiet build
  local flag="0"
  if [[ "${GENIE_NATIVE:-}" == "1" ]]; then flag="1"; fi
  mkdir -p "$REPO_ROOT/dist"
  local wheel
  wheel="$(build_wheel "$build_py" "$REPO_ROOT/dist" "$flag")"
  if [[ "$flag" == "1" ]]; then
    "$build_py" "$SMOKE" --check-wheel "$wheel" --expect-native
  else
    "$build_py" "$SMOKE" --check-wheel "$wheel" --expect-pure
  fi
  phase "wheel built: $wheel"
}

cmd_verify() {
  local tree_before
  tree_before="$(git -C "$REPO_ROOT" status --porcelain)"

  make_prefix "$WORK/tools-venv"
  local build_py="$WORK/tools-venv/bin/python"
  "$build_py" -m pip install --quiet build

  # --- flag-off: pure-Python wheel -------------------------------------
  phase "flag-off build (GENIE_NATIVE unset)"
  local off_wheel off_py on_wheel on_py edit_py
  off_wheel="$(build_wheel "$build_py" "$WORK/dist-off" "0")"
  "$build_py" "$SMOKE" --check-wheel "$off_wheel" --expect-pure

  phase "flag-off clean-prefix install + smoke"
  make_prefix "$WORK/off-venv"
  off_py="$WORK/off-venv/bin/python"
  "$off_py" -m pip install --quiet "$off_wheel" pytest
  prefix_smoke "$off_py" --expect-pure
  prefix_replay "$off_py"

  # --- flag-on: native wheel -------------------------------------------
  phase "flag-on build (GENIE_NATIVE=1)"
  on_wheel="$(build_wheel "$build_py" "$WORK/dist-on" "1")"
  "$build_py" "$SMOKE" --check-wheel "$on_wheel" --expect-native

  phase "flag-on clean-prefix install + GENIE_NATIVE=1 smoke"
  make_prefix "$WORK/on-venv"
  on_py="$WORK/on-venv/bin/python"
  "$on_py" -m pip install --quiet "$on_wheel" pytest
  prefix_smoke "$on_py" --expect-native GENIE_NATIVE=1
  prefix_replay "$on_py" GENIE_NATIVE=1

  # --- editable install with no toolchain on PATH ----------------------
  phase "editable install with no toolchain on PATH"
  make_prefix "$WORK/edit-venv"
  edit_py="$WORK/edit-venv/bin/python"
  local scrubbed="$WORK/edit-venv/bin" dir tool
  while IFS= read -r dir; do
    [[ -n "$dir" ]] || continue
    local keep=1
    for tool in cmake ninja cc gcc g++ clang clang++; do
      if [[ -x "$dir/$tool" ]]; then keep=0; break; fi
    done
    [[ "$keep" == "1" ]] && scrubbed="$scrubbed:$dir"
  done < <(echo "$PATH" | tr ':' '\n' | awk '!seen[$0]++')
  if PATH="$scrubbed" command -v cmake >/dev/null 2>&1 \
    || PATH="$scrubbed" command -v ninja >/dev/null 2>&1; then
    fail "PATH scrub left cmake/ninja visible"
  fi
  PATH="$scrubbed" "$edit_py" -m pip install --quiet -e "$REPO_ROOT" \
    || fail "editable pip install -e . failed with no toolchain on PATH"
  (cd "$WORK" && env GENIE_MODE=mock "$edit_py" "$SMOKE" --expect-pure)

  # --- repo-fit: the tree must be untouched -----------------------------
  local tree_after
  tree_after="$(git -C "$REPO_ROOT" status --porcelain)"
  [[ "$tree_after" == "$tree_before" ]] \
    || fail "repo tree changed by verify: [$tree_after] vs [$tree_before]"
  phase "repo tree untouched"

  phase "all green: flag-off pure, flag-on native, editable no-toolchain"
}

case "${1:-verify}" in
  build) cmd_build ;;
  verify) cmd_verify ;;
  *)
    echo "usage: $0 [build|verify]" >&2
    exit 2
    ;;
esac
