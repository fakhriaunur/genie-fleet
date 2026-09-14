"""Vulture whitelist: names used dynamically (factories, plugs)."""

from genie_fleet import _native
from genie_fleet.api import create_app

whitelist_create_app = create_app
whitelist_native_available = _native.NATIVE_AVAILABLE
whitelist_should_use_native = _native.should_use_native
