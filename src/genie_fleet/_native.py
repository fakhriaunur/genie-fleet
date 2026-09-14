"""Native dispatch shim (M2 seam probe, flagged off by default).

Tries to locate the compiled ``genie_fleet_native`` extension (pybind11).
When absent — the normal path in this repo — ``NATIVE_AVAILABLE`` is False
and every caller falls back to the pure-Python matrix core. Absence is
expected, never an error: the Python path stays byte-identical either way.
"""

from __future__ import annotations

import importlib.util
import logging

#: True only when the compiled extension is importable in this process.
NATIVE_AVAILABLE: bool = importlib.util.find_spec("genie_fleet_native") is not None

_warned_fallback = False


def should_use_native(use_native_flag: bool) -> bool:
    """Fail-safe gate for the flagged-off native path.

    Returns True only when the caller requested native AND the extension
    is present. When requested but absent, logs one warning and returns
    False so callers fall back to Python. Never raises.
    """
    global _warned_fallback
    if not use_native_flag:
        return False
    if NATIVE_AVAILABLE:
        return True
    if not _warned_fallback:
        logging.getLogger("genie_fleet.native").warning(
            "GENIE_NATIVE=1 but genie_fleet_native is absent; "
            "falling back to pure-Python matrix core"
        )
        _warned_fallback = True
    return False
