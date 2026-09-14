"""Minimal stdlib logging. One configure call, one logger factory."""

from __future__ import annotations

import logging
from typing import Any

_configured = False


def configure_logging(level: str = "info") -> None:
    """Configure root logging once (idempotent)."""
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _configured = True


def get_logger(name: str) -> logging.LoggerAdapter[logging.Logger]:
    """Return a logger adapter with a stable service field."""
    return logging.LoggerAdapter(logging.getLogger(name), {"service": name})


def log_extra(**fields: Any) -> dict[str, Any]:
    """Helper to keep structured-log call sites uniform."""
    return dict(fields)
