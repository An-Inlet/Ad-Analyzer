"""Explicit immutable offline bundle; no caller credentials or real network transport."""

import json
from collections.abc import Callable
from datetime import datetime
from typing import Literal

import httpx
from fastapi import HTTPException, Request
from pydantic import Field, SecretStr, model_validator

from app.planning_documents.common import Digest, Frozen, Positive
from app.planning_documents.google_budget_fixture_runtime import FixturePage
from app.planning_documents.google_budget_http import GoogleBudgetHTTPContext, GoogleBudgetHTTPRead
from app.planning_documents.google_budget_http_proof import (
    HTTP_PROFILE,
    V24_QUERIES,
    GoogleBudgetHTTPProofV1,
    GoogleBudgetHTTPTicketV1,
    request_body,
)
from app.planning_documents.google_budget_read import MAX_PROOF_BYTES
from app.settings import settings


class GoogleBudgetHTTPFixture(Frozen):
    provenance: Literal["mock_http"] = "mock_http"
    profile_digest: Digest = HTTP_PROFILE
    workspace_id: Positive
    source_binding_digest: Digest
    privacy_revision: int = Field(strict=True, ge=0)
    pages: tuple[FixturePage, ...] = Field(min_length=3, max_length=30)

    @model_validator(mode="after")
    def bounded(self) -> "GoogleBudgetHTTPFixture":
        keys = [(p.query_kind, p.request_cursor) for p in self.pages]
        if (
            self.profile_digest != HTTP_PROFILE
            or len(keys) != len(set(keys))
            or sum(len(p.response_json.encode()) for p in self.pages) > MAX_PROOF_BYTES - 32768
        ):
            raise ValueError("exact bounded mock HTTP fixture required")
        return self

    def acquire(
        self,
        ticket: GoogleBudgetHTTPTicketV1,
        revalidate: Callable[[GoogleBudgetHTTPTicketV1], None],
        clock: Callable[[], datetime],
        guard: Callable[[], None],
    ) -> GoogleBudgetHTTPProofV1:
        if (
            ticket.binding.workspace_id != self.workspace_id
            or ticket.source_binding_digest != self.source_binding_digest
            or ticket.privacy_revision != self.privacy_revision
            or ticket.profile_digest != self.profile_digest
        ):
            raise HTTPException(409, "Mock HTTP bundle does not match the owned source.")
        sequence = 0

        def handle(request: httpx.Request) -> httpx.Response:
            nonlocal sequence
            guard()
            if request.method != "POST" or str(request.url) != ticket.account.endpoint():
                raise ValueError("mock endpoint mismatch")
            payload = json.loads(request.content)
            for page in self.pages:
                if (
                    payload.get("query") == V24_QUERIES[page.query_kind]
                    and request.content
                    == request_body(page.query_kind, page.request_cursor).encode()
                ):
                    sequence += 1
                    return httpx.Response(
                        200,
                        content=page.response_json.encode(),
                        headers={
                            "content-type": "application/json",
                            "request-id": f"mock-{sequence}",
                        },
                    )
            raise ValueError("mock page unavailable")

        def enabled() -> bool:
            guard()
            return True

        def context(req: GoogleBudgetHTTPTicketV1) -> GoogleBudgetHTTPContext:
            return GoogleBudgetHTTPContext(
                ticket_digest=req.digest(),
                expires_at=req.expires_at,
                access_token=SecretStr("inlet-synthetic-mock-only"),
                developer_token=SecretStr("inlet-synthetic-mock-only"),
            )

        return GoogleBudgetHTTPRead(
            context, revalidate, transport=httpx.MockTransport(handle), enabled=enabled, clock=clock
        )(ticket)


def configured_http_fixture(request: Request) -> GoogleBudgetHTTPFixture | None:
    bundle = getattr(request.app.state, "google_budget_http_fixture", None)
    if (
        settings.customer_google_budget_http_mode != "mock_http"
        or settings.customer_planning_policy != "v6"
        or type(bundle) is not GoogleBudgetHTTPFixture
    ):
        return None
    return bundle


def require_http_fixture(
    request: Request,
    expected: GoogleBudgetHTTPFixture | None = None,
) -> GoogleBudgetHTTPFixture:
    bundle = configured_http_fixture(request)
    if bundle is None or (expected is not None and bundle is not expected):
        raise HTTPException(503, "Mock HTTP budget observations are unavailable.")
    return bundle
