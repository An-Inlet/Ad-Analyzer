"""Injected-only v22 setting acquisition. Fixture provenance is never authentication."""

import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol

from pydantic import (
    AwareDatetime,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from app.planning_documents.common import Digest, Id, NoAuthority, fingerprint
from app.planning_documents.context import ReportingWindow
from app.planning_documents.events import VersionBinding
from app.planning_documents.google_budget_owner_contracts import _instant, _originals
from app.publication.contracts import fingerprint as source_fingerprint
from app.publication.execution_contracts import ExecutionAccount

Query = Literal["customer", "campaign", "campaignBudget"]
QUERIES: dict[Query, str] = {
    "customer": "SELECT customer.resource_name, customer.currency_code, customer.time_zone, "
    "customer.status, customer.manager FROM customer",
    "campaign": "SELECT campaign.resource_name, campaign.campaign_budget, campaign.status "
    "FROM campaign WHERE campaign.status IN ('ENABLED', 'PAUSED', 'REMOVED')",
    "campaignBudget": "SELECT campaign_budget.resource_name, campaign_budget.amount_micros, "
    "campaign_budget.total_amount_micros, campaign_budget.explicitly_shared, "
    "campaign_budget.reference_count, campaign_budget.period, campaign_budget.status, "
    "campaign_budget.type FROM campaign_budget "
    "WHERE campaign_budget.status IN ('ENABLED', 'REMOVED')",
}
PROFILE = fingerprint(
    "inlet.google-budget-read-profile.v1", dict(api_version="v22", queries=QUERIES)
)
MAX_PROOF_BYTES = 384 * 1024


class ReadValue(NoAuthority):
    @model_serializer(mode="wrap")
    def checked(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        result: dict[str, Any] = handler(type(self).model_validate(self))
        return result

    @model_validator(mode="before")
    @classmethod
    def originals(cls, value: Any) -> Any:
        _originals(value)
        return value


class GoogleBudgetReadTicketV1(ReadValue):
    nonce: Id
    binding: VersionBinding
    account: ExecutionAccount
    privacy_revision: int = Field(strict=True, ge=0)
    reporting_window: ReportingWindow
    prepared_at: AwareDatetime
    expires_at: AwareDatetime
    api_version: Literal["v22"] = "v22"
    profile_digest: Digest = PROFILE
    provenance: Literal["injected_fixture"] = "injected_fixture"

    @field_validator("prepared_at", "expires_at", mode="before")
    @classmethod
    def instant(cls, value: Any) -> datetime:
        return _instant(value)

    @model_validator(mode="after")
    def exact(self) -> "GoogleBudgetReadTicketV1":
        if (
            self.account.workspace_id != self.binding.workspace_id
            or self.account.account.platform != "google_ads"
            or not re.fullmatch(r"[0-9]{10}", self.account.external_advertiser_id)
            or self.profile_digest != PROFILE
            or not self.reporting_window.ends_at_exclusive <= self.prepared_at < self.expires_at
            or self.expires_at - self.prepared_at > timedelta(minutes=5)
        ):
            raise ValueError("invalid Google budget acquisition ticket")
        return self

    def source_digest(self) -> str:
        return source_fingerprint("inlet.planning-source.v1", self.account.model_dump(mode="json"))


class GoogleBudgetReadPageV1(ReadValue):
    query_kind: Query
    request_cursor: str | None = Field(max_length=4096, strict=True)
    requested_at: AwareDatetime
    received_at: AwareDatetime
    response_json: str = Field(strict=True, min_length=2, max_length=262144)

    @field_validator("requested_at", "received_at", mode="before")
    @classmethod
    def instant(cls, value: Any) -> datetime:
        return _instant(value)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError("duplicate response JSON key")
    return dict(pairs)


def _reject_constant(value: str) -> Any:
    raise ValueError("non-JSON numeric constant")


def _integer(value: Any) -> int:
    if type(value) is not str or not re.fullmatch(r"0|[1-9][0-9]{0,15}", value):
        raise ValueError("explicit canonical int64 string required")
    number = int(value)
    if number > 10**15:
        raise ValueError("native integer exceeds bound")
    return number


def _resource(value: Any, customer: str, collection: str) -> str:
    if type(value) is not str or not re.fullmatch(
        "customers/" + customer + "/" + collection + r"/[0-9]{1,32}", value
    ):
        raise ValueError("exact owned Google resource required")
    return value


def decode(page: GoogleBudgetReadPageV1, customer: str) -> tuple[list[dict[str, Any]], str | None]:
    if len(page.response_json.encode()) > 262144:
        raise ValueError("response byte bound")
    raw = json.loads(page.response_json, object_pairs_hook=_object, parse_constant=_reject_constant)
    if not isinstance(raw, dict) or set(raw) - {"results", "nextPageToken", "fieldMask"}:
        raise ValueError("unselected response fields")
    if "fieldMask" in raw:
        # Retain a mask only when it exactly names this fixed query's selected fields.
        selected = QUERIES[page.query_kind].split(" FROM ")[0].removeprefix("SELECT ").split(", ")

        def camel(value: str) -> str:
            return re.sub(r"_([a-z])", lambda m: m[1].upper(), value)

        if raw["fieldMask"] != ",".join(camel(field) for field in selected):
            raise ValueError("response field mask mismatch")
    cursor = raw.get("nextPageToken")
    if cursor is not None and (type(cursor) is not str or not 1 <= len(cursor) <= 4096):
        raise ValueError("invalid response cursor")
    if "nextPageToken" in raw and cursor is None:
        raise ValueError("null response cursor")
    rows = raw.get("results")
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValueError("explicit bounded response rows required")
    result = []
    fields = {
        "customer": {"resourceName", "currencyCode", "timeZone", "status", "manager"},
        "campaign": {"resourceName", "campaignBudget", "status"},
        "campaignBudget": {
            "resourceName",
            "amountMicros",
            "explicitlyShared",
            "referenceCount",
            "period",
            "status",
            "type",
        },
    }[page.query_kind]
    for envelope in rows:
        if not isinstance(envelope, dict) or set(envelope) != {page.query_kind}:
            raise ValueError("unselected response row")
        row = envelope[page.query_kind]
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("explicit exact selected field presence required")
        if page.query_kind == "customer":
            if (
                row["resourceName"] != "customers/" + customer
                or row["manager"] is not False
                or row["status"] != "ENABLED"
                or type(row["currencyCode"]) is not str
                or not re.fullmatch(r"[A-Z]{3}", row["currencyCode"])
                or type(row["timeZone"]) is not str
                or not 1 <= len(row["timeZone"]) <= 64
            ):
                raise ValueError("customer setting mismatch")
        elif page.query_kind == "campaign":
            _resource(row["resourceName"], customer, "campaigns")
            _resource(row["campaignBudget"], customer, "campaignBudgets")
            if row["status"] not in ("ENABLED", "PAUSED", "REMOVED"):
                raise ValueError("unknown campaign status")
        else:
            _resource(row["resourceName"], customer, "campaignBudgets")
            _integer(row["amountMicros"])
            _integer(row["referenceCount"])
            if (
                type(row["explicitlyShared"]) is not bool
                or row["period"] != "DAILY"
                or row["status"] not in ("ENABLED", "REMOVED")
                or row["type"] != "STANDARD"
            ):
                raise ValueError("unsupported budget profile")
        result.append(row)
    return result, cursor


class GoogleBudgetReadProofV1(ReadValue):
    schema_version: Literal["inlet.google-budget-read-proof.v1"] = (
        "inlet.google-budget-read-proof.v1"
    )
    ticket: GoogleBudgetReadTicketV1
    pages: tuple[GoogleBudgetReadPageV1, ...] = Field(min_length=3, max_length=30)

    @model_validator(mode="after")
    def exact(self) -> "GoogleBudgetReadProofV1":
        if sum(len(p.response_json.encode()) for p in self.pages) > MAX_PROOF_BYTES - 32768:
            raise ValueError("aggregate read proof byte bound")
        payload = dict(
            ticket=self.ticket.model_dump(mode="json"),
            pages=[p.model_dump(mode="json") for p in self.pages],
        )
        if len(json.dumps(payload, ensure_ascii=False).encode()) > MAX_PROOF_BYTES - 1024:
            raise ValueError("aggregate read proof byte bound")
        self.rows()
        return self

    def rows(self) -> dict[Query, list[dict[str, Any]]]:
        output: dict[Query, list[dict[str, Any]]] = {}
        index, last = 0, self.ticket.prepared_at
        for kind in QUERIES:
            values: list[dict[str, Any]] = []
            cursor: str | None = None
            seen: set[str] = set()
            for _ in range(10):
                if index >= len(self.pages):
                    raise ValueError("missing terminal query page")
                page = self.pages[index]
                index += 1
                if (
                    page.query_kind != kind
                    or page.request_cursor != cursor
                    or not last <= page.requested_at <= page.received_at < self.ticket.expires_at
                ):
                    raise ValueError("query order, cursor or read timestamp mismatch")
                last = page.received_at
                rows, cursor = decode(page, self.ticket.account.external_advertiser_id)
                values.extend(rows)
                if len(values) > 200 or len({r["resourceName"] for r in values}) != len(values):
                    raise ValueError("duplicate resources or query capacity")
                if cursor is None:
                    break
                if cursor in seen:
                    raise ValueError("response cursor loop")
                seen.add(cursor)
            else:
                raise ValueError("query pagination incomplete")
            output[kind] = values
        if index != len(self.pages) or len(output["customer"]) != 1:
            raise ValueError("extra pages or nonunique customer")
        budgets = {r["resourceName"] for r in output["campaignBudget"]}
        if any(r["campaignBudget"] not in budgets for r in output["campaign"]):
            raise ValueError("campaign budget join incomplete")
        return output


class InjectedGoogleSearch(Protocol):
    def __call__(
        self, ticket: GoogleBudgetReadTicketV1, query: str, cursor: str | None, /
    ) -> str: ...


def read_google_budget(
    ticket: GoogleBudgetReadTicketV1,
    search: InjectedGoogleSearch,
    clock: Callable[[], datetime],
) -> GoogleBudgetReadProofV1:
    ticket = GoogleBudgetReadTicketV1.model_validate(ticket)
    pages: list[GoogleBudgetReadPageV1] = []
    last = ticket.prepared_at
    for kind, query in QUERIES.items():
        cursor: str | None = None
        seen: set[str] = set()
        resource_names: set[str] = set()
        for _ in range(10):
            start = _instant(clock())
            if not last <= start < ticket.expires_at:
                raise ValueError("read ticket expired")
            response = search(ticket, query, cursor)
            end = _instant(clock())
            if not start <= end < ticket.expires_at:
                raise ValueError("read ticket expired")
            last = end
            page = GoogleBudgetReadPageV1(
                query_kind=kind,
                request_cursor=cursor,
                requested_at=start,
                received_at=end,
                response_json=response,
            )
            pages.append(page)
            rows, cursor = decode(page, ticket.account.external_advertiser_id)
            for row in rows:
                if row["resourceName"] in resource_names:
                    raise ValueError("duplicate query resource")
                resource_names.add(row["resourceName"])
            if len(resource_names) > 200 or (cursor is not None and cursor in seen):
                raise ValueError("query capacity or cursor loop")
            if cursor is not None:
                seen.add(cursor)
            if sum(len(p.response_json.encode()) for p in pages) > MAX_PROOF_BYTES - 32768:
                raise ValueError("aggregate read proof byte bound")
            if cursor is None:
                break
        else:
            raise ValueError("query pagination incomplete")
    return GoogleBudgetReadProofV1(ticket=ticket, pages=tuple(pages))
