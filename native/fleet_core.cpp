// M2 scaffold: same greedy nearest-cover re-route as matrix.py,
// expressed over SoA float arrays. NOT compiled or imported yet;
// the Python core remains the submission path until the parity gate
// in native/NOTES.md passes. Requires pybind11 3.1.0 (see NOTES.md).

#include <cmath>
#include <limits>
#include <string>
#include <vector>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

namespace {

// Home bases mirror TECH_HOME in matrix.py: Maya, Rio, Sam.
constexpr double HOME_X[3] = {0.0, 10.0, 0.0};
constexpr double HOME_Y[3] = {0.0, 0.0, 10.0};

inline double dist(double x, double y, int tech) {
    const double dx = x - HOME_X[tech];
    const double dy = y - HOME_Y[tech];
    return std::sqrt(dx * dx + dy * dy);
}

int nearest_cover(double x, double y, int absent) {
    int best = -1;
    double best_d = std::numeric_limits<double>::infinity();
    for (int tech = 0; tech < 3; ++tech) {
        if (tech == absent) {
            continue;
        }
        const double d = dist(x, y, tech);
        // Ties broken by lower tech index, matching the sorted-name
        // order Maya < Rio < Sam used by the Python core.
        if (d < best_d) {
            best_d = d;
            best = tech;
        }
    }
    return best;
}

}  // namespace

std::vector<int> reassign_sick_leave_soa(
    const std::vector<double>& xs,
    const std::vector<double>& ys,
    const std::vector<int>& owners,
    int absent
) {
    std::vector<int> result = owners;
    for (std::size_t i = 0; i < owners.size(); ++i) {
        if (owners[i] == absent) {
            result[i] = nearest_cover(xs[i], ys[i], absent);
        }
    }
    return result;
}

double fleet_fuel_soa(
    const std::vector<double>& xs,
    const std::vector<double>& ys,
    const std::vector<int>& owners
) {
    double total = 0.0;
    for (std::size_t i = 0; i < owners.size(); ++i) {
        total += dist(xs[i], ys[i], owners[i]);
    }
    return total;
}

PYBIND11_MODULE(genie_fleet_native, m) {
    m.doc() = "M2 scaffold: greedy nearest-cover re-route over SoA arrays.";
    m.def(
        "reassign_sick_leave_soa",
        &reassign_sick_leave_soa,
        "Re-route one tech's rows to the nearest cover (SoA arrays)."
    );
    m.def(
        "fleet_fuel_soa",
        &fleet_fuel_soa,
        "Total fuel over SoA arrays (sum of distances to owner bases)."
    );
}
