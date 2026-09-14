cmake_minimum_required(VERSION 3.21)

# M7 hardening, scaffold only: NOT wired into pyproject/mise install
# paths. Configure checks run in a TEMP build dir only, never in-tree.
project(genie_fleet_native CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Position-independent code so the pybind11 module links anywhere.
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Strict warnings on our own sources. pybind11 headers come in as
# SYSTEM includes via pybind11_add_module, so they stay quiet.
if(MSVC)
  add_compile_options(/W4)
else()
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Versions are pinned by native/NOTES.md: pybind11 3.1.0, pyarrow 25.x.
find_package(pybind11 3.1.0 CONFIG REQUIRED)

# The header is listed so declaration/definition mismatches fail at
# configure/compile time (the cpp includes fleet_core.hpp first).
pybind11_add_module(genie_fleet_native fleet_core.cpp fleet_core.hpp)

# Intentionally NO install()/export() target: the extension stays
# unwired and GENIE_NATIVE stays off until a parity-gate milestone
# proves the native path and wires it deliberately.
