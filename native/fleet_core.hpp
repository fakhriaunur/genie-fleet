// M7 hardening: declares exactly what native/fleet_core.cpp defines.
//
// The cpp includes this header FIRST so any declaration/definition
// mismatch fails at compile time. Scaffold only: NOT wired into
// pyproject/mise install paths; the pure-Python matrix core stays the
// shipped path until the parity gate in native/NOTES.md passes.

#ifndef GENIE_FLEET_FLEET_CORE_HPP
#define GENIE_FLEET_FLEET_CORE_HPP

#include <vector>

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

#endif  // GENIE_FLEET_FLEET_CORE_HPP
