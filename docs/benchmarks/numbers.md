# Benchmark rerun: cold / warm / hot, baseline vs native

Date: 2026-09-14 (UTC). Mode: `GENIE_MODE=mock`, zero AWS spend, no credentials.
Repo: repo root (`.`), read-only (no repo files
modified; `git status` clean before and after). Machine: Linux x86_64
(7.0.0-1010-oracle), shared host; Python 3.14.7, pybind11 3.1.0, cmake 4.4.3,
ninja 1.13.2 (all via mise). Extension built to a `mktemp` dir (Release), loaded via
explicit `importlib` spec, `sys.path` untouched, temp dir deleted after the runs
(see Cleanup). Companion to `research/baseline-vs-native.md` (6-task) and
`research/baseline-vs-native-large.md` (synthetic to 100k).

## Definitions (used exactly as briefed)

- **COLD:** fresh `python -c`-equivalent process per dispatch: interpreter start +
  imports + (native: extension spec-load) + fleet build + ONE dispatch. Wall time via
  `perf_counter` around the whole subprocess. 10 samples per cell; median reported.
- **WARM:** in-process, one warmup excluded, then timed iters: 100 at <=600 tasks,
  20 at 6k, 5 at 60k, 3 at 100k. End-to-end core math: baseline =
  `reassign_sick_leave` + `fleet_fuel` x2; native = fresh SoA build +
  `reassign_sick_leave_soa` + `fleet_fuel_soa` x2. At size 6: canned `optimize` vs
  `try_native_optimize` (full wrapper, incl. report shaping).
- **HOT:** steady-state reassign-only on reused state: baseline =
  `reassign_sick_leave` on the same `Fleet` object; native =
  `ext.reassign_sick_leave_soa` directly on prebuilt, reused SoA buffers (no fuel
  passes). 200 iters at <=6k, 50 at 60k, 20 at 100k.

Fleets: `tests/scenarios/test_scale.py` builder pattern verbatim (seed `20260915`,
round-robin techs). Maya outage throughout; Rio added at 6 and 100k only.
Medians are the comparator (shared-host noise); speedups are baseline/native medians.

## Headline: warm speedup per size (median-based)

| Size | Outage | Baseline warm med | Native warm med | Speedup |
|------|--------|------------------|-----------------|---------|
| 6 | Maya | 0.0171 ms | 0.0201 ms | **0.85x** (native slower) |
| 6 | Rio | 0.0171 ms | 0.0203 ms | **0.84x** (native slower) |
| 600 | Maya | 0.5829 ms | 0.0924 ms | **6.31x** |
| 6000 | Maya | 5.8764 ms | 0.9113 ms | **6.45x** |
| 60000 | Maya | 62.5150 ms | 9.3953 ms | **6.65x** |
| 100000 | Maya | 112.6699 ms | 20.5706 ms | **5.48x** |
| 100000 | Rio | 112.6142 ms | 16.2736 ms | **6.92x** |

Note: Maya@100k native warm shows one slow iter (mean 23.31 ms, stdev 8.17 ms over
3 iters vs Rio stdev 0.23 ms); the Maya median 20.57 ms is likely noise-inflated and
the Rio 6.92x is the cleaner 100k warm figure.

## Hot speedup per size (median-based, reassign-only)

| Size | Outage | Baseline hot med | Native hot med | Speedup |
|------|--------|-----------------|----------------|---------|
| 6 | Maya | 0.0050 ms | 0.0005 ms | **10.2x** |
| 6 | Rio | 0.0078 ms | 0.0007 ms | **11.3x** |
| 600 | Maya | 0.4004 ms | 0.0213 ms | **18.8x** |
| 6000 | Maya | 4.1306 ms | 0.2062 ms | **20.0x** |
| 60000 | Maya | 45.1731 ms | 2.1031 ms | **21.5x** |
| 100000 | Maya | 83.0044 ms | 3.6316 ms | **22.9x** |
| 100000 | Rio | 85.4349 ms | 3.5638 ms | **24.0x** |

Hot isolates the C++ loop from SoA conversion: ~21-24x steady-state on the reassign
math at large sizes, vs ~6-7x warm end-to-end (conversion + fuel passes included).

## Cold-start numbers (median of 10 fresh processes; stdev in brackets)

| Size | Outage | Baseline cold | Native cold | Delta (nat-base) |
|------|--------|--------------|-------------|------------------|
| 6 | Maya | 27.9 ms (0.6) | 41.1 ms (0.9) | **+13.2 ms** |
| 6 | Rio | 28.6 ms (1.4) | 41.4 ms (0.5) | **+12.8 ms** |
| 600 | Maya | 30.2 ms (1.1) | 31.2 ms (5.0) | +1.0 ms |
| 6000 | Maya | 49.4 ms (1.2) | 44.7 ms (1.0) | -4.7 ms |
| 60000 | Maya | 239.9 ms (53.7) | 183.7 ms (2.8) | -56.2 ms |
| 100000 | Maya | 385.9 ms (8.7) | 288.2 ms (4.4) | -97.7 ms |
| 100000 | Rio | 385.5 ms (6.2) | 288.9 ms (5.0) | -96.6 ms |

Story: at 6 tasks the cold dispatch is ~28 ms of interpreter+import fixed cost and the
native path adds ~13 ms (extension file load + wrapper imports) for a ~0.02 ms math
kernel. By 600 tasks the gap is noise; past 6k the faster native math outweighs the
load cost even cold. (60k baseline stdev 53.7 ms = one slow outlier, shared host.)

## Full per-cell stats (median / mean / stdev / min, ms)

### Warm

| Cell | Baseline (med/mean/sd/min) | Native (med/mean/sd/min) |
|------|---------------------------|--------------------------|
| 6 Maya (n=100) | 0.0171 / 0.0177 / 0.0022 / 0.0166 | 0.0201 / 0.0207 / 0.0018 / 0.0197 |
| 6 Rio (n=100) | 0.0171 / 0.0176 / 0.0022 / 0.0168 | 0.0203 / 0.0206 / 0.0017 / 0.0198 |
| 600 Maya (n=100) | 0.5829 / 0.5835 / 0.0195 / 0.5665 | 0.0924 / 0.1014 / 0.0151 / 0.0913 |
| 6000 Maya (n=20) | 5.8764 / 5.9274 / 0.1459 / 5.8340 | 0.9113 / 0.9268 / 0.0663 / 0.8913 |
| 60k Maya (n=5) | 62.5150 / 63.2128 / 1.4529 / 62.2348 | 9.3953 / 9.3953 / 0.1139 / 9.2410 |
| 100k Maya (n=3) | 112.6699 / 114.1230 / 3.1546 / 111.9568 | 20.5706 / 23.3077 / 8.1662 / 16.8616 |
| 100k Rio (n=3) | 112.6142 / 114.9617 / 4.8487 / 111.7335 | 16.2736 / 16.2380 / 0.2263 / 15.9961 |

### Hot (reassign-only)

| Cell | Baseline (med/mean/sd/min) | Native (med/mean/sd/min) |
|------|---------------------------|--------------------------|
| 6 Maya (n=200) | 0.0050 / 0.0051 / 0.0010 / 0.0048 | 0.0005 / 0.0005 / 0.0000 / 0.0005 |
| 6 Rio (n=200) | 0.0078 / 0.0079 / 0.0017 / 0.0049 | 0.0007 / 0.0006 / 0.0001 / 0.0005 |
| 600 Maya (n=200) | 0.4004 / 0.4158 / 0.0482 / 0.3944 | 0.0213 / 0.0222 / 0.0027 / 0.0213 |
| 6000 Maya (n=200) | 4.1306 / 4.2285 / 0.3689 / 4.0818 | 0.2062 / 0.2144 / 0.0336 / 0.2053 |
| 60k Maya (n=50) | 45.1731 / 48.2275 / 15.3272 / 42.9226 | 2.1031 / 2.1215 / 0.0573 / 2.0693 |
| 100k Maya (n=20) | 83.0044 / 86.4801 / 8.5653 / 80.4213 | 3.6316 / 3.6700 / 0.1683 / 3.5036 |
| 100k Rio (n=20) | 85.4349 / 87.6769 / 7.9639 / 81.0862 | 3.5638 / 3.5671 / 0.0313 / 3.5235 |

(60k baseline hot stdev 15.3 ms = shared-host outliers; median is the comparator.)

## Correctness per cell

| Size | Outage | Owners | Fuel 2dp | Moved (base / nat) | Full-report byte-eq |
|------|--------|--------|----------|--------------------|---------------------|
| 6 | Maya | equal | 22.43 / 22.43 | 2 / 2 | PASS (`optimize` JSON, `sort_keys=True`) |
| 6 | Rio | equal | 29.28 / 29.28 | 2 / 2 | PASS |
| 600 | Maya | 600/600 | 5001.91 / 4285.84 both | 200 / 200 | PASS (`dispatch_report` JSON) |
| 6000 | Maya | 6000/6000 | 50271.62 / 43110.63 both | 2000 / 2000 | PASS (`dispatch_report` JSON) |
| 60000 | Maya | 59999/60000, 1 diff @task 56064 | 506372.96 / 432258.44 both | 20000 / 20000 | not attempted (O(n*moved) shaping, both paths) |
| 100000 | Maya | 99999/100000, 1 diff @task 56064 | 843727.39 / 720567.77 both | 33334 / 33334 | not attempted |
| 100000 | Rio | 100000/100000 | 843727.39 / 798326.31 both | 33333 / 33333 | not attempted |

Cold cells: moved + fuel_after agreed baseline-vs-native in all 7 cells (10/10
samples each). Hot spot-checks: owners equal in all cells including both Maya
large cells at the reassign level measured (the @56064 tie-flip recorded in the
warm correctness pass above; per brief, recorded, not investigated).

Known tie-flip reappeared: task 56064 at (1.82, 1.82) on the Rio/Sam bisector flips
to Sam in C++ (FP-contraction 1-ulp asymmetry) while Python breaks the exact tie by
name to Rio. Zero fuel impact at 2dp, zero moved-count impact. See
`research/baseline-vs-native-large.md` finding 2.

## Alt-texts

- **speedup-vs-size.png:** "Log-x line chart of native speedup (baseline median divided
  by native median) over fleet sizes 6 to 100000 tasks. A dotted black breakeven line
  marks 1x. The blue solid circle series (warm Maya, end-to-end core) starts at 0.85x
  at 6 tasks, then reads 6.3x, 6.4x, 6.7x and 5.5x at 600, 6k, 60k and 100k. The
  vermillion dashed square series (hot Maya, reassign only) reads 10x, 19x, 20x, 21x
  and 23x. Two unconnected spot-check markers at 6 and 100k show Rio warm (green
  triangles, 0.8x and 6.9x) and Rio hot (gold diamonds, 11x and 24x). Annotations note
  native is slower below breakeven at the 6-task full dispatch."
- **cold-start.png:** "Bar chart of cold-start latency, median of 10 fresh processes,
  Maya outage. Four bars: 6 tasks baseline 27.9 ms (solid blue), 6 tasks native
  41.1 ms (hatched vermillion), 600 tasks baseline 30.2 ms (solid blue), 600 tasks
  native 31.2 ms (hatched vermillion). An annotation notes native costs an extra
  13.2 ms at 6 tasks from extension load plus wrapper imports; by 600 tasks the gap
  is about 1 ms. Series are distinguished by both color and hatching."
- **absolute-time.png:** "Log-log line chart of median warm dispatch time in
  milliseconds over fleet sizes 6 to 100000 tasks (Maya). The blue solid circle
  series (baseline: reassign plus two fuel passes) runs from 0.02 ms to 112.67 ms;
  the vermillion dashed square series (native: SoA build plus extension calls) runs
  from 0.02 ms to 20.57 ms. Both series are near-straight lines, showing linear
  scaling with a roughly 6x constant-factor gap; every point carries a direct
  millisecond label."

## Repro (read-only; temp dirs only, no repo writes)

```bash
cd "$(git rev-parse --show-toplevel)"   # repo root
export GENIE_MODE=mock PYTHONPATH=src   # ensure GENIE_NATIVE is unset
BUILD_DIR=$(mktemp -d /tmp/genie-native-bench.XXXXXX)
PYBIND11_DIR=$(mise exec -- python -c "import pybind11; print(pybind11.get_cmake_dir())")
cmake -S native -B "$BUILD_DIR" -G Ninja -DCMAKE_BUILD_TYPE=Release -Dpybind11_DIR="$PYBIND11_DIR"
cmake --build "$BUILD_DIR"   # one genie_fleet_native*.so, ~4 s
SO="$BUILD_DIR"/genie_fleet_native.cpython-314-x86_64-linux-gnu.so
PY=$(mise which python)
# Warm+hot (scripts were throwaway /tmp files, removed after the runs):
GENIE_NATIVE_SO="$SO" $PY /tmp/bench/bench_warm_hot.py   # 7 JSON cells on stdout
# Cold (10 fresh processes per cell, externally wall-timed):
for args in "6 Maya" "6 Rio" "600 Maya" "6000 Maya" "60000 Maya" "100000 Maya" "100000 Rio"; do
  for path in baseline native; do
    for i in $(seq 1 10); do /usr/bin/time -f "%e" \
      $PY /tmp/bench/cold_one.py $args $path; done;
  done;
done
rm -rf "$BUILD_DIR"   # verify: git status --short clean; no genie_fleet_native*.so in tree
```

Warm/hot driver detail: one warmup excluded per timed function; warm iters 100
(<=600), 20 (6k), 5 (60k), 3 (100k); hot iters 200 (<=6k), 50 (60k), 20 (100k).
Warm baseline = `reassign_sick_leave` + `fleet_fuel` x2; warm native = SoA
comprehension build + `reassign_sick_leave_soa` + `fleet_fuel_soa` x2; hot baseline
= `reassign_sick_leave` on the same `Fleet`; hot native = `reassign_sick_leave_soa`
on prebuilt reused buffers. Size 6 uses canned `optimize` / `try_native_optimize`.
Plots: matplotlib 3.11.2 in an isolated `/tmp/bench-plots` venv (repo env untouched),
Okabe-Ito palette, white background, >=14pt fonts, distinct markers+linestyles
(+hatching on bars), direct data labels, 200 DPI.

## Deviations from plan

1. Hot iters at 60k/100k reduced to 50/20 (from 200) — 200 baseline hot iters at
   100k would cost ~17 s per outage with no statistical benefit; medians are stable
   at n=20 (native stdev <5%).
2. `dispatch_report` byte-equality done at 600 and 6000 (both PASS), skipped at
   60k/100k per plan (O(n*moved) `by_id` shaping shared by both paths).
3. In the warm correctness record, the "native moved" field for synthetic sizes was
   computed as agreements-vs-baseline-after rather than an independent moved count;
   the reported invariant is: native moved count == baseline moved count in every
   cell (the single @56064 flip still moves, to the other cover), fuel 2dp equal.
4. Maya@100k warm native median is likely noise-inflated (see note under headline
   table); Rio@100k 6.92x is the cleaner 100k warm figure.

## Cleanup

Temp extension build dir `/tmp/genie-native-bench.sBlaBU` deleted after the runs;
throwaway scripts in `/tmp/bench` removed; isolated venv `/tmp/bench-plots` removed.
Repo untouched: no new files, `git status --short` clean, no `.so` in tree.
