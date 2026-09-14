// M7 hardening: declares exactly what native/fleet_core.cpp defines.
//
// The cpp includes this header FIRST so any declaration/definition
// mismatch fails at compile time. Scaffold only: NOT wired into
// pyproject/mise install paths; the pure-Python matrix core stays the
// shipped path until the parity gate in native/NOTES.md passes.

#ifndef GENIE_FLEET_FLEET_CORE_HPP
#define GENIE_FLEET_FLEET_CORE_HPP

#include <cstdint>
#include <vector>

#include <pybind11/pybind11.h>

// Re-route one tech's rows to the nearest covering tech (SoA arrays).
// Mirrors the greedy nearest-cover re-route in matrix.py.
std::vector<int> reassign_sick_leave_soa(
    const std::vector<double>& xs,
    const std::vector<double>& ys,
    const std::vector<int>& owners,
    int absent);

// Total fuel over SoA arrays (sum of distances to owner bases).
double fleet_fuel_soa(
    const std::vector<double>& xs,
    const std::vector<double>& ys,
    const std::vector<int>& owners);

// S4 zero-copy Arrow boundary: the task columns arrive as shared buffers
// (float64 xs/ys, int64 owners) that C++ reads in place — no per-row
// Python objects cross. Reassignment indices are written into the
// caller-owned out buffer (int64, same length), so they come back as a
// view of memory the caller already holds.

// Evidence helper for tests: the data pointer C++ observes through the
// boundary. Tests assert it equals the Arrow data buffer address.
std::uintptr_t buffer_data_ptr(pybind11::buffer buf);

// Re-route one tech's rows, reading shared column buffers in place and
// writing int64 indices into out (must hold the same task count).
void reassign_sick_leave_buffers(
    pybind11::buffer xs,
    pybind11::buffer ys,
    pybind11::buffer owners,
    int absent,
    pybind11::buffer out);

// Total fuel over shared column buffers (sum of distances to bases).
double fleet_fuel_buffers(
    pybind11::buffer xs, pybind11::buffer ys, pybind11::buffer owners);

#endif  // GENIE_FLEET_FLEET_CORE_HPP
