// M2 scaffold: same greedy nearest-cover re-route as matrix.py,
// expressed over SoA float arrays. NOT compiled or imported yet;
// the Python core remains the submission path until the parity gate
// in native/NOTES.md passes. Requires pybind11 3.1.0 (see NOTES.md).

#include "fleet_core.hpp"

#include <cmath>
#include <cstdint>
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

// S4 zero-copy Arrow boundary. Column layout: xs/ys are float64 buffers,
// owners/out are int64 buffers, all 1-D with the same task count. Every
// pointer below aliases the caller's shared buffers — nothing is copied
// and no per-row Python object is touched.
namespace {

struct shared_columns {
    const double* xs;
    const double* ys;
    const std::int64_t* owners;
    std::size_t count;
};

bool is_int64_format(const std::string& format) {
    return format == "q" || format == "l";
}

shared_columns require_shared_columns(
    py::buffer xs_buf, py::buffer ys_buf, py::buffer owners_buf
) {
    py::buffer_info xs = xs_buf.request();
    py::buffer_info ys = ys_buf.request();
    py::buffer_info owners = owners_buf.request();
    if (xs.ndim != 1 || ys.ndim != 1 || owners.ndim != 1) {
        throw py::value_error("S4 boundary: columns must be 1-D buffers");
    }
    if (xs.format != "d" || xs.itemsize != 8) {
        throw py::value_error("S4 boundary: xs must be a float64 buffer");
    }
    if (ys.format != "d" || ys.itemsize != 8) {
        throw py::value_error("S4 boundary: ys must be a float64 buffer");
    }
    if (!is_int64_format(owners.format) || owners.itemsize != 8) {
        throw py::value_error("S4 boundary: owners must be an int64 buffer");
    }
    const auto count = static_cast<std::size_t>(xs.size);
    if (static_cast<std::size_t>(ys.size) != count ||
        static_cast<std::size_t>(owners.size) != count) {
        throw py::value_error("S4 boundary: column lengths disagree");
    }
    return shared_columns{
        static_cast<const double*>(xs.ptr),
        static_cast<const double*>(ys.ptr),
        static_cast<const std::int64_t*>(owners.ptr),
        count,
    };
}

std::int64_t* require_out_buffer(py::buffer out_buf, std::size_t count) {
    py::buffer_info out = out_buf.request();
    if (out.ndim != 1) {
        throw py::value_error("S4 boundary: out must be a 1-D buffer");
    }
    if (!is_int64_format(out.format) || out.itemsize != 8) {
        throw py::value_error("S4 boundary: out must be an int64 buffer");
    }
    if (static_cast<std::size_t>(out.size) != count) {
        throw py::value_error("S4 boundary: out length must match columns");
    }
    if (out.readonly) {
        throw py::value_error("S4 boundary: out buffer must be writable");
    }
    return static_cast<std::int64_t*>(out.ptr);
}

}  // namespace

std::uintptr_t buffer_data_ptr(py::buffer buf) {
    py::buffer_info info = buf.request();
    return reinterpret_cast<std::uintptr_t>(info.ptr);
}

void reassign_sick_leave_buffers(
    py::buffer xs_buf,
    py::buffer ys_buf,
    py::buffer owners_buf,
    int absent,
    py::buffer out_buf
) {
    const shared_columns cols =
        require_shared_columns(xs_buf, ys_buf, owners_buf);
    std::int64_t* out = require_out_buffer(out_buf, cols.count);
    for (std::size_t i = 0; i < cols.count; ++i) {
        if (cols.owners[i] == absent) {
            out[i] = nearest_cover(cols.xs[i], cols.ys[i], absent);
        } else {
            out[i] = cols.owners[i];
        }
    }
}

double fleet_fuel_buffers(
    py::buffer xs_buf, py::buffer ys_buf, py::buffer owners_buf
) {
    const shared_columns cols =
        require_shared_columns(xs_buf, ys_buf, owners_buf);
    double total = 0.0;
    for (std::size_t i = 0; i < cols.count; ++i) {
        total += dist(cols.xs[i], cols.ys[i], static_cast<int>(cols.owners[i]));
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
    m.def(
        "buffer_data_ptr",
        &buffer_data_ptr,
        "Data pointer C++ observes through a buffer (test evidence)."
    );
    m.def(
        "reassign_sick_leave_buffers",
        &reassign_sick_leave_buffers,
        "Re-route one tech's rows reading shared column buffers in place; "
        "indices are written into the caller-owned out buffer."
    );
    m.def(
        "fleet_fuel_buffers",
        &fleet_fuel_buffers,
        "Total fuel reading shared column buffers in place."
    );
}
