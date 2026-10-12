"""Best-effort fixed-vocabulary diagnostics; no authority or customer data retained."""

import json
import logging
from collections.abc import Callable, Coroutine
from contextlib import suppress
from contextvars import ContextVar
from typing import Any, Literal

from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

PlanningDiagnosticPhase = Literal["lock", "replay", "pre_cas", "post_flush", "unspecified"]
_ROUTE_NAMES = {
    "generate_plan": "generate",
    "read_plan": "current",
    "plan_versions": "history",
    "read_version": "version",
}
_ROUTES = frozenset({"generate", "current", "history", "version", "unspecified"})
_PHASES = frozenset({"lock", "replay", "pre_cas", "post_flush", "unspecified"})
_route: ContextVar[str] = ContextVar("planning_diagnostic_route", default="unspecified")
_logger = logging.getLogger("inlet.planning.authority")


def _label(value: object, allowed: frozenset[str]) -> str:
    # No subclass hash/equality/repr is allowed to execute during normalization.
    return value if type(value) is str and value in allowed else "unspecified"


def emit_expiry(
    *, phase: object, cause: Literal["fact_age_outside_window", "session_expired"]
) -> None:
    try:
        if type(cause) is not str or cause not in {"fact_age_outside_window", "session_expired"}:
            return
        record = {
            "event": "planning_authority_expired",
            "schema_version": 1,
            "route": _label(_route.get(), _ROUTES),
            "phase": _label(phase, _PHASES),
            "cause": cause,
            "session_predicate": "not_evaluated"
            if cause == "fact_age_outside_window"
            else "expired",
            "status": 409,
        }
        _logger.warning(json.dumps(record, sort_keys=True, separators=(",", ":")))
    except Exception:
        # No fallback logger: a broken filter/formatter/handler must not replace 409.
        pass


def _emit_conflict() -> None:
    with suppress(Exception):
        _logger.warning(
            json.dumps(
                {
                    "event": "planning_route_conflict",
                    "schema_version": 1,
                    "route": _label(_route.get(), _ROUTES),
                    "reason": "other_conflict",
                    "status": 409,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )


class PlanningDiagnosticRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()
        route = (
            _ROUTE_NAMES.get(self.name, "unspecified") if type(self.name) is str else "unspecified"
        )

        async def handler(request: Request) -> Response:
            token = _route.set(route)
            try:
                return await original(request)
            except HTTPException as error:
                if (
                    type(error.status_code) is int
                    and error.status_code == 409
                    and not (
                        type(error.detail) is str and error.detail == "planning_authority_expired"
                    )
                ):
                    _emit_conflict()
                raise
            finally:
                _route.reset(token)

        return handler
