"""FastAPI dispatch board viewer. Mock mode boots with no credentials."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from starlette.responses import Response

from genie_fleet import __version__
from genie_fleet.agent import run_dispatch_request, run_multi_dispatch_request
from genie_fleet.logging import configure_logging, get_logger
from genie_fleet.matrix import CANNED_ABSENT_TECH, TECH_HOME
from genie_fleet.settings import Settings, load_settings
from genie_fleet.tools import tool_metadata


class DispatchRequest(BaseModel):
    """Dispatcher constraint input: who called in sick."""

    absent_tech: str = Field(default=CANNED_ABSENT_TECH, min_length=1)
    absent_techs: list[str] | None = Field(
        default=None,
        description=(
            "Optional multi-outage list. When absent or empty, the singular "
            "absent_tech path runs unchanged; when non-empty, the union of "
            "the listed districts is re-routed."
        ),
    )
    notes: str = Field(default="", max_length=500)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory (uvicorn `--factory` entrypoint)."""
    resolved = settings if settings is not None else load_settings()
    configure_logging(resolved.log_level)
    logger = get_logger("genie_fleet.api")

    app = FastAPI(title="genie-fleet", version=__version__)

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.headers.get(
            "X-Request-Id", str(uuid.uuid4())
        )
        return response

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, object]:
        report: dict[str, object] = {
            "mode": "live" if resolved.is_live else "mock",
            "version": __version__,
            "tool": tool_metadata(),
            "techs": sorted(TECH_HOME),
        }
        logger.info("readiness_report mode=%s", report["mode"])
        return report

    @app.post("/dispatch")
    async def dispatch(request: DispatchRequest) -> dict[str, object]:
        if request.absent_techs:
            for tech in request.absent_techs:
                if tech not in TECH_HOME:
                    return {
                        "error": f"unknown tech: {tech!r}",
                        "known_techs": sorted(TECH_HOME),
                    }
            try:
                outcome = run_multi_dispatch_request(
                    request.absent_techs, settings=resolved
                )
            except ValueError as exc:
                return {
                    "error": str(exc),
                    "known_techs": sorted(TECH_HOME),
                }
            logger.info(
                "dispatch path=%s absent=%s",
                outcome["path"],
                outcome["absent_tech"],
            )
            response_multi: dict[str, object] = {
                "path": outcome["path"],
                "absent_tech": outcome["absent_tech"],
                "report": outcome["report"],
                "board": outcome["board"],
            }
            return response_multi
        if request.absent_tech not in TECH_HOME:
            return {
                "error": f"unknown tech: {request.absent_tech!r}",
                "known_techs": sorted(TECH_HOME),
            }
        outcome = run_dispatch_request(
            f"{request.absent_tech} called in sick. {request.notes}".strip(),
            settings=resolved,
        )
        logger.info(
            "dispatch path=%s absent=%s", outcome["path"], outcome["absent_tech"]
        )
        response: dict[str, object] = {
            "path": outcome["path"],
            "absent_tech": outcome["absent_tech"],
            "report": outcome["report"],
            "board": outcome["board"],
        }
        return response

    return app
