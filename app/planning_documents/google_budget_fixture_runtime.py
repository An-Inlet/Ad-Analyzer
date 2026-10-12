"""Explicit in-process synthetic pages; no provider transport or production mode."""

from typing import Literal

from fastapi import HTTPException, Request
from pydantic import Field, model_validator

from app.planning_documents.common import Digest, Frozen, Positive
from app.planning_documents.google_budget_read import (
    MAX_PROOF_BYTES,
    PROFILE,
    QUERIES,
    GoogleBudgetReadTicketV1,
    Query,
)
from app.settings import settings


class FixturePage(Frozen):
    query_kind: Query
    request_cursor: str | None = Field(strict=True, max_length=4096)
    response_json: str = Field(strict=True, min_length=2, max_length=262144)


class GoogleBudgetFixture(Frozen):
    """One exact synthetic account/source, installed only by an offline harness.

    Pages have no provider acquisition timestamp. The retained request interval
    measures replay of this fixture, not freshness of advertising settings.
    """

    provenance: Literal["injected_fixture"] = "injected_fixture"
    profile_digest: Digest = PROFILE
    workspace_id: Positive
    source_binding_digest: Digest
    privacy_revision: int = Field(strict=True, ge=0)
    pages: tuple[FixturePage, ...] = Field(min_length=3, max_length=30)

    @model_validator(mode="after")
    def bounded(self) -> "GoogleBudgetFixture":
        keys = [(page.query_kind, page.request_cursor) for page in self.pages]
        if (
            self.profile_digest != PROFILE
            or len(keys) != len(set(keys))
            or sum(len(page.response_json.encode()) for page in self.pages) > MAX_PROOF_BYTES
        ):
            raise ValueError("exact bounded synthetic Google pages required")
        return self

    def search(self, ticket: GoogleBudgetReadTicketV1, query: str, cursor: str | None) -> str:
        if (
            ticket.binding.workspace_id != self.workspace_id
            or ticket.source_digest() != self.source_binding_digest
            or ticket.privacy_revision != self.privacy_revision
            or ticket.profile_digest != self.profile_digest
            or ticket.provenance != self.provenance
        ):
            raise HTTPException(409, "Configured fixture does not match the owned source.")
        for page in self.pages:
            if QUERIES[page.query_kind] == query and page.request_cursor == cursor:
                return page.response_json
        raise HTTPException(503, "Configured fixture page is unavailable.")


def configured_fixture(request: Request) -> GoogleBudgetFixture | None:
    fixture = getattr(request.app.state, "google_budget_observation_fixture", None)
    if (
        settings.customer_google_budget_observation_mode != "injected_fixture"
        or settings.customer_planning_policy != "v6"
        or type(fixture) is not GoogleBudgetFixture
    ):
        return None
    return fixture


def require_fixture(
    request: Request, expected: GoogleBudgetFixture | None = None
) -> GoogleBudgetFixture:
    fixture = configured_fixture(request)
    if fixture is None or (expected is not None and fixture is not expected):
        raise HTTPException(503, "Synthetic budget observations are unavailable.")
    return fixture
