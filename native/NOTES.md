# M2 native scaffold — packaging wired (M10), runtime still flagged off

This directory is the C++ Transform seam. M10 wires it into packaging via
a best-effort hatchling custom hook (root `hatch_build.py`, approach B):
the default wheel build never shells out and stays pure-Python, while
`GENIE_NATIVE=1` temp-builds the extension and places
`genie_fleet_native<EXT_SUFFIX>` at the wheel TOP LEVEL (never inside
`src/genie_fleet`, which `_native.py` does not probe). Any toolchain
failure warns and still ships the pure-Python wheel. The sdist ships
these C++ sources. Revert packaging by deleting `hatch_build.py` plus
the `hooks.custom` stanza in `pyproject.toml`.

Runtime stance is unchanged: `GENIE_NATIVE` stays off by default, the
pure-Python `matrix.py` core remains the serving path, and nothing here
is imported unless the flag is on and the extension is present.

## Pinned versions

- `pybind11 3.1.0` (Aug 6 2026) — module boundary for `fleet_core.cpp`.
- `pyarrow 25.x` (25.0.1, Aug 10 2026, cp314 wheels) — columnar boundary.

Neither appears in `pyproject.toml` dependencies on purpose: adding them
would change the install footprint before the seam is proven.

## Zero-copy Arrow boundary intent

When (and only when) the parity gate below passes, the intended call path
is: Python builds task columns as Arrow arrays → the pybind11 module reads
the underlying SoA float buffers in place (no per-row Python objects across
the boundary) → reassignment indices come back as an Arrow/buffer view →
`matrix.py` shapes the unchanged `dispatch_report` JSON. The JSON contract
never changes; only the compute location moves.

## Parity gate (must ALL hold before any activation)

1. `mise run replay` green: golden fixture
   `tests/replay/fixtures/dispatch_golden.json` matches exactly.
2. `fuel_before`, `fuel_after`, and `tasks_moved` from the native path are
   identical to the Python `optimize()` output for every tech outage
   (Maya, Rio, Sam).
3. `tests/unit/test_native_parity.py` passes with the native toolchain
   present (flag on uses native; flag off uses Python; outputs equal).

Until then the flag stays off and this directory stays a sketch: if C++
breaks replay, we hold the Transform and ship Python per the spec.
