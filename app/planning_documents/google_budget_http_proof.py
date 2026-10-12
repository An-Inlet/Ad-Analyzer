"""V24 mock-HTTP transcript. Never a live attestation or a legacy V22 observation."""

import hashlib
import json
from datetime import timedelta
from types import MappingProxyType
from typing import Any, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.planning_documents.common import Digest, Id, Positive, fingerprint
from app.planning_documents.events import VersionBinding
from app.planning_documents.google_budget_owner_contracts import _instant
from app.planning_documents.google_budget_read import (
    MAX_PROOF_BYTES,
    QUERIES,
    GoogleBudgetReadPageV1,
    Query,
    ReadValue,
    _object,
    _reject_constant,
    decode,
)
from app.publication.contracts import fingerprint as source_fingerprint

V24_QUERIES = MappingProxyType(dict(QUERIES))
HTTP_PROFILE = fingerprint(
    "inlet.google-budget-http-profile.v1",
    dict(api_version="v24", queries=dict(V24_QUERIES), method="POST", format="rest-json"),
)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def request_body(kind: Query, cursor: str | None) -> str:
    body = {"query": V24_QUERIES[kind]}
    if cursor is not None:
        body["pageToken"] = cursor
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class GoogleBudgetHTTPAccount(ReadValue):
    workspace_id: Positive
    account_id: Positive
    connection_id: Positive
    connection_version: str = Field(strict=True, min_length=1, max_length=100)
    native_customer_id: str = Field(strict=True, pattern=r"^[0-9]{10}$")
    platform: Literal["google_ads"] = "google_ads"

    def source_digest(self) -> str:
        return source_fingerprint("inlet.planning-source.v1", dict(
            workspace_id=self.workspace_id,
            account=dict(account_id=self.account_id, connection_id=self.connection_id,
                         platform=self.platform),
            external_advertiser_id=self.native_customer_id,
            connection_version=self.connection_version,
        ))

    def endpoint(self) -> str:
        return ("https://googleads.googleapis.com/v24/customers/"
                f"{self.native_customer_id}/googleAds:search")


class GoogleBudgetHTTPTicketV1(ReadValue):
    schema_version: Literal["inlet.google-budget-http-ticket.v1"] = (
        "inlet.google-budget-http-ticket.v1"
    )
    nonce: Id
    binding: VersionBinding
    account: GoogleBudgetHTTPAccount
    source_binding_digest: Digest
    privacy_revision: int = Field(strict=True, ge=0)
    prepared_at: AwareDatetime
    expires_at: AwareDatetime
    api_version: Literal["v24"] = "v24"
    profile_digest: Digest = HTTP_PROFILE
    provenance: Literal["mock_http"] = "mock_http"

    @field_validator("prepared_at", "expires_at", mode="before")
    @classmethod
    def instant(cls, value: Any) -> Any:
        return _instant(value)

    @model_validator(mode="after")
    def bound(self) -> "GoogleBudgetHTTPTicketV1":
        if (
            self.account.workspace_id != self.binding.workspace_id
            or self.source_binding_digest != self.account.source_digest()
            or self.profile_digest != HTTP_PROFILE
            or not timedelta(0) < self.expires_at - self.prepared_at <= timedelta(seconds=60)
        ):
            raise ValueError("exact bounded v24 ticket required")
        return self


class GoogleBudgetHTTPPageV1(GoogleBudgetReadPageV1):
    endpoint: str = Field(strict=True, min_length=1, max_length=128)
    method: Literal["POST"] = "POST"
    request_body_digest: Digest
    response_digest: Digest
    request_id: str = Field(strict=True, pattern=r"^[A-Za-z0-9_-]{1,128}$")
    status: Literal[200] = 200

    @model_validator(mode="after")
    def commitments(self) -> "GoogleBudgetHTTPPageV1":
        if (
            self.request_body_digest != sha(request_body(self.query_kind, self.request_cursor))
            or self.response_digest != sha(self.response_json)
        ):
            raise ValueError("HTTP transcript digest mismatch")
        return self


def decoded(
    page: GoogleBudgetHTTPPageV1, customer: str,
) -> tuple[list[dict[str, Any]], str | None, int | None]:
    raw = json.loads(page.response_json, object_pairs_hook=_object, parse_constant=_reject_constant)
    if not isinstance(raw, dict):
        raise ValueError("response object required")
    counts: dict[str, int] = {}
    for key in ("queryResourceConsumption", "totalResultsCount"):
        if key in raw:
            value = raw.pop(key)
            if (type(value) is not str or not value.isascii() or not value.isdecimal()
                    or len(value) > 19 or str(int(value)) != value or int(value) > 2**63 - 1):
                raise ValueError("canonical int64 metadata required")
            counts[key] = int(value)
    # The old decoder is a pure selected-field parser, not a V22 provenance proof.
    # Retain all original V24 bytes above; remove only the two validated metadata cells.
    selected = GoogleBudgetReadPageV1(
        query_kind=page.query_kind, request_cursor=page.request_cursor,
        requested_at=page.requested_at, received_at=page.received_at,
        response_json=json.dumps(raw, separators=(",", ":")),
    )
    rows, cursor = decode(selected, customer)
    return rows, cursor, counts.get("totalResultsCount")


class GoogleBudgetHTTPProofV1(ReadValue):
    schema_version: Literal["inlet.google-budget-http-proof.v1"] = (
        "inlet.google-budget-http-proof.v1"
    )
    provenance: Literal["mock_http"] = "mock_http"
    provider_authentication: Literal["not_verified"] = "not_verified"
    implementation: Literal["not_assessed"] = "not_assessed"
    ticket: GoogleBudgetHTTPTicketV1
    pages: tuple[GoogleBudgetHTTPPageV1, ...] = Field(min_length=3, max_length=30)

    @model_validator(mode="after")
    def transcript(self) -> "GoogleBudgetHTTPProofV1":
        if sum(len(p.response_json.encode()) for p in self.pages) > MAX_PROOF_BYTES - 32768:
            raise ValueError("HTTP proof capacity")
        payload = dict(ticket=self.ticket.model_dump(mode="json"),
                       pages=[p.model_dump(mode="json") for p in self.pages])
        if len(json.dumps(payload, ensure_ascii=False).encode()) > MAX_PROOF_BYTES - 1024:
            raise ValueError("HTTP proof envelope capacity")
        index, last = 0, self.ticket.prepared_at
        inventory: dict[Query, list[dict[str, Any]]] = {}
        request_ids: set[str] = set()
        for kind in V24_QUERIES:
            cursor: str | None = None
            cursors: set[str] = set()
            rows: list[dict[str, Any]] = []
            totals: set[int] = set()
            for _ in range(10):
                if index == len(self.pages):
                    raise ValueError("missing terminal response")
                page = self.pages[index]
                index += 1
                if (page.endpoint != self.ticket.account.endpoint() or page.query_kind != kind
                        or page.request_cursor != cursor or page.request_id in request_ids
                        or not last <= page.requested_at <= page.received_at
                        < self.ticket.expires_at):
                    raise ValueError("HTTP transcript binding mismatch")
                request_ids.add(page.request_id)
                last = page.received_at
                values, cursor, total = decoded(page, self.ticket.account.native_customer_id)
                rows.extend(values)
                if total is not None:
                    totals.add(total)
                if len(rows) > 200 or len({r["resourceName"] for r in rows}) != len(rows):
                    raise ValueError("duplicate or over-bound resource")
                if cursor is None:
                    break
                if cursor in cursors:
                    raise ValueError("cursor loop")
                cursors.add(cursor)
            else:
                raise ValueError("query page bound")
            if totals and totals != {len(rows)}:
                raise ValueError("result count mismatch")
            inventory[kind] = rows
        if index != len(self.pages) or len(inventory["customer"]) != 1:
            raise ValueError("extra responses or nonunique customer")
        budgets = {r["resourceName"] for r in inventory["campaignBudget"]}
        if any(r["campaignBudget"] not in budgets for r in inventory["campaign"]):
            raise ValueError("incomplete budget linkage")
        return self
