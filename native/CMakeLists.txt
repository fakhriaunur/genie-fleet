cmake_minimum_required(VERSION 3.21)

# M2 scaffold only: NOT wired into pyproject/mise. No build runs here.
project(genie_fleet_native CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Versions are pinned by native/NOTES.md: pybind11 3.1.0, pyarrow 25.x.
find_package(pybind11 3.1.0 CONFIG REQUIRED)

pybind11_add_module(genie_fleet_native fleet_core.cpp)
