"""Environment-bound settings. Mock mode needs no secrets; live mode fails closed."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from the environment."""

    mode: str = "mock"
    strands_model_id: str = ""
    aws_region: str = "us-west-2"
    api_port: int = 8002
    log_level: str = "info"
    #: Opt-in to the M2 native extension (GENIE_NATIVE=1). Default off;
    #: when requested but absent, callers log once and use Python.
    use_native: bool = False

    def __post_init__(self) -> None:
        if self.is_live and not self.strands_model_id:
            raise RuntimeError(
                "GENIE_MODE=live requires STRANDS_MODEL_ID; refusing to boot live "
                "without a model (fail-closed)."
            )

    @property
    def is_live(self) -> bool:
        """Whether this process may touch Bedrock / AgentCore."""
        return self.mode.strip().lower() == "live"


def _parse_native_flag(raw: str) -> bool:
    """Parse GENIE_NATIVE: opt-in spellings select native; all else off."""
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_settings(env: dict[str, str] | None = None) -> Settings:
    """Build settings from the environment (injectable mapping for tests)."""
    source = env if env is not None else os.environ
    return Settings(
        mode=source.get("GENIE_MODE", "mock"),
        strands_model_id=source.get("STRANDS_MODEL_ID", ""),
        aws_region=source.get("AWS_REGION", "us-west-2"),
        api_port=int(source.get("API_PORT", "8002")),
        log_level=source.get("LOG_LEVEL", "info"),
        use_native=_parse_native_flag(source.get("GENIE_NATIVE", "0")),
    )
