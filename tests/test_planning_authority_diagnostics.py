"""Fixed diagnostics preserve original predicates and actual ASGI context isolation."""

import asyncio
import json
import logging
import threading
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from app.customers.access import CustomerPrincipal
from app.planning_documents import authority
from app.planning_documents import authority_diagnostics as diagnostics
from fastapi import APIRouter, Depends, FastAPI, HTTPException


def identity() -> tuple[CustomerPrincipal, authority.IdentityFact]:
    principal = cast(
        CustomerPrincipal,
        SimpleNamespace(
            user=SimpleNamespace(
                id="PRIVATE-USER",
                issuer="PRIVATE-ISSUER",
                subject="PRIVATE-SUBJECT",
                status="active",
            ),
            session=SimpleNamespace(
                user_id="PRIVATE-USER",
                digest="PRIVATE-DIGEST",
                authenticated_at=123,
                revoked_at=None,
                expires_at=200.0,
            ),
        ),
    )
    fact = authority.IdentityFact(
        "PRIVATE-USER", "PRIVATE-ISSUER", "PRIVATE-SUBJECT", "PRIVATE-DIGEST", 123, 100.0
    )
    return principal, fact


def events(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [
        json.loads(r.getMessage()) for r in caplog.records if r.name == "inlet.planning.authority"
    ]


@pytest.mark.parametrize("age", [6.0, -1.0, float("nan"), float("inf")])
def test_age_refusal_does_not_read_session_or_wall_clock(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, age: float
) -> None:
    principal, fact = identity()
    del cast(Any, principal.session).expires_at

    def wall() -> float:
        raise AssertionError("short-circuited clock was evaluated")

    monkeypatch.setattr(authority, "time", SimpleNamespace(monotonic=lambda: 100 + age, time=wall))
    with pytest.raises(HTTPException) as error:
        authority.final(principal, fact, diagnostic_phase="post_flush")
    assert (error.value.status_code, error.value.detail) == (409, "planning_authority_expired")
    assert events(caplog) == [
        dict(
            event="planning_authority_expired",
            schema_version=1,
            route="unspecified",
            phase="post_flush",
            cause="fact_age_outside_window",
            session_predicate="not_evaluated",
            status=409,
        )
    ]
    assert "PRIVATE" not in caplog.text


@pytest.mark.parametrize("wall,expired", [(199.0, False), (200.0, True)])
def test_inclusive_age_five_then_original_session_predicate(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, wall: float, expired: bool
) -> None:
    principal, fact = identity()
    calls: list[str] = []

    def monotonic() -> float:
        calls.append("monotonic")
        return 105.0

    def now() -> float:
        calls.append("wall")
        return wall

    monkeypatch.setattr(authority, "time", SimpleNamespace(monotonic=monotonic, time=now))
    if expired:
        with pytest.raises(HTTPException) as error:
            authority.final(principal, fact)
        assert error.value.detail == "planning_authority_expired"
        assert events(caplog)[0]["cause"] == "session_expired"
    else:
        authority.final(principal, fact)
        assert events(caplog) == []
    assert calls == ["monotonic", "wall"]


@pytest.mark.parametrize("failure", ["revoked", "clock", "wall-clock"])
def test_original_nonexpiry_failure_has_no_diagnostic(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, failure: str
) -> None:
    principal, fact = identity()
    sentinel = RuntimeError("PRIVATE-UNEXPECTED")

    def broken() -> float:
        raise sentinel

    monkeypatch.setattr(
        authority,
        "time",
        SimpleNamespace(
            monotonic=(lambda: 105.0) if failure == "wall-clock" else broken, time=broken
        ),
    )
    if failure == "revoked":
        cast(Any, principal.session).revoked_at = 1
        with pytest.raises(HTTPException) as error:
            authority.final(principal, fact)
        assert error.value.status_code == 401
    else:
        with pytest.raises(RuntimeError) as unexpected:
            authority.final(principal, fact)
        assert unexpected.value is sentinel
    assert events(caplog) == []


class Hostile:
    def __hash__(self) -> int:
        raise AssertionError("hash")

    def __eq__(self, other: object) -> bool:
        raise AssertionError("equality")

    def __repr__(self) -> str:
        raise AssertionError("repr")


class HostileString(str):
    def __hash__(self) -> int:
        raise AssertionError("hash")

    def __eq__(self, other: object) -> bool:
        raise AssertionError("equality")


@pytest.mark.parametrize(
    "label",
    [Hostile(), HostileString("post_flush"), b"post_flush", True],
    ids=["object", "subclass", "bytes", "bool"],
)
def test_labels_are_exact_type_before_any_user_operation(
    caplog: pytest.LogCaptureFixture, label: object
) -> None:
    diagnostics.emit_expiry(phase=label, cause="fact_age_outside_window")
    assert events(caplog)[0]["phase"] == "unspecified"


@pytest.mark.parametrize("stage", ["logger", "filter", "formatter", "handler", "json"])
def test_diagnostic_failure_never_replaces_authority_refusal(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    principal, fact = identity()
    monkeypatch.setattr(authority, "time", SimpleNamespace(monotonic=lambda: 106.0))

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("PRIVATE-LOG-FAILURE")

    logger = logging.Logger("isolated-planning-diagnostic")
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    monkeypatch.setattr(diagnostics, "_logger", logger)
    if stage == "json":
        monkeypatch.setattr(diagnostics, "json", SimpleNamespace(dumps=broken))
    elif stage == "logger":
        monkeypatch.setattr(logger, "warning", broken)
    elif stage == "filter":
        monkeypatch.setattr(logger, "filter", broken)
    elif stage == "formatter":
        monkeypatch.setattr(handler, "format", broken)
        monkeypatch.setattr(handler, "handleError", broken)
    else:
        monkeypatch.setattr(handler, "emit", broken)
    with pytest.raises(HTTPException) as error:
        authority.final(principal, fact)
    assert (error.value.status_code, error.value.detail) == (409, "planning_authority_expired")


def test_actual_asgi_sync_dependency_overlap_and_context_cleanup(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    app = FastAPI()
    router = APIRouter(route_class=diagnostics.PlanningDiagnosticRoute)
    barrier = threading.Barrier(2)
    principal, fact = identity()
    monkeypatch.setattr(authority, "time", SimpleNamespace(monotonic=lambda: 106.0))

    def dependency() -> None:
        barrier.wait(timeout=10)
        authority.final(principal, fact, diagnostic_phase="lock")

    def generate_plan(_: None = Depends(dependency)) -> None:
        raise AssertionError("expired dependency reached endpoint")

    def read_plan() -> None:
        barrier.wait(timeout=10)
        authority.final(principal, fact, diagnostic_phase="pre_cas")

    def healthy() -> dict[str, str]:
        return {"route": diagnostics._route.get()}

    router.add_api_route("/one", generate_plan, methods=["POST"])
    router.add_api_route("/two", read_plan, methods=["GET"])
    router.add_api_route("/healthy", healthy, methods=["GET"])
    app.include_router(router)

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://local"
        ) as client:
            one, two = await asyncio.gather(client.post("/one"), client.get("/two"))
            assert one.status_code == two.status_code == 409
            assert one.json() == two.json() == {"detail": "planning_authority_expired"}
            assert (await client.get("/healthy")).json() == {"route": "unspecified"}
        assert diagnostics._route.get() == "unspecified"

    asyncio.run(run())
    assert {(e["route"], e["phase"], e["cause"]) for e in events(caplog)} == {
        ("generate", "lock", "fact_age_outside_window"),
        ("current", "pre_cas", "fact_age_outside_window"),
    }
    assert len(events(caplog)) == 2 and "PRIVATE" not in caplog.text


@pytest.mark.parametrize(
    "name,route",
    [("plan_versions", "history"), ("read_version", "version"), ("other", "unspecified")],
)
@pytest.mark.parametrize(
    "detail",
    [{"secret": "PRIVATE-DETAIL"}, Hostile(), HostileString("planning_authority_expired")],
    ids=["mapping", "object", "subclass"],
)
def test_actual_asgi_conflict_original_exception_and_logger_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    name: str,
    route: str,
    detail: Any,
) -> None:
    app = FastAPI()
    router = APIRouter(route_class=diagnostics.PlanningDiagnosticRoute)
    sentinel = HTTPException(409, detail)
    seen: list[bool] = []

    def endpoint() -> None:
        raise sentinel

    @app.exception_handler(HTTPException)
    async def original_error(request: Any, error: HTTPException) -> Any:
        from starlette.responses import JSONResponse

        seen.append(error is sentinel)
        return JSONResponse({"status": "refused"}, status_code=error.status_code)

    router.add_api_route("/conflict", endpoint, name=name)
    app.include_router(router)

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://local"
        ) as client:
            assert (await client.get("/conflict")).status_code == 409
        assert diagnostics._route.get() == "unspecified"

    asyncio.run(run())
    assert events(caplog) == [
        dict(
            event="planning_route_conflict",
            schema_version=1,
            route=route,
            reason="other_conflict",
            status=409,
        )
    ]
    assert "PRIVATE" not in caplog.text

    def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("PRIVATE-LOG-FAILURE")

    monkeypatch.setattr(diagnostics._logger, "warning", broken)
    asyncio.run(run())
    assert seen == [True, True]
