"""Mocked exact HTTP protocol; never real credentials, live transport or event admission."""

import json
import logging
import traceback
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.planning_documents.google_budget_events import GoogleBudgetObservationV1
from app.planning_documents.google_budget_http import (
    GoogleBudgetHTTPContext,
    GoogleBudgetHTTPUnavailable,
    configured_mock_budget_read,
)
from app.planning_documents.google_budget_http_proof import (
    V24_QUERIES,
    GoogleBudgetHTTPAccount,
    GoogleBudgetHTTPProofV1,
    GoogleBudgetHTTPTicketV1,
    request_body,
    sha,
)
from app.planning_documents.google_budget_read import GoogleBudgetReadProofV1
from app.settings import Settings
from pydantic import SecretStr, ValidationError

from tests.google_budget_event_fixture import history as events
from tests.google_budget_read_fixture import Search

NOW = datetime(2026, 10, 12, 12, tzinfo=UTC)
SECRET = "fixture-only-not-a-real-credential"


def ticket() -> GoogleBudgetHTTPTicketV1:
    account = GoogleBudgetHTTPAccount(
        workspace_id=1, account_id=2, connection_id=3, connection_version="source-v1",
        native_customer_id="1234567890",
    )
    return GoogleBudgetHTTPTicketV1(
        nonce="a" * 32,
        binding=dict(workspace_id=1, plan_id="b" * 32, version=1,
                     document_digest="c" * 64, action_key="budget_review", action_digest="d" * 64),
        account=account, source_binding_digest=account.source_digest(), privacy_revision=4,
        prepared_at=NOW, expires_at=NOW + timedelta(seconds=60),
    )


class Harness:
    def __init__(self, damage: str = "none") -> None:
        self.damage = damage
        self.now = NOW
        self.revalidations = 0
        self.stream_closed = False
        self.replacement_calls = 0
        self.calls: list[httpx.Request] = []
        self.config = Settings(_env_file=None, INLET_CUSTOMER_GOOGLE_BUDGET_HTTP_MODE="mock_http")
        self.source = Search("1234567890", amount=0)
        self.context = GoogleBudgetHTTPContext(
            ticket_digest=ticket().digest(), expires_at=NOW + timedelta(seconds=30),
            access_token=SecretStr(SECRET), developer_token=SecretStr(SECRET),
            login_customer_id="9999999999",
        )
        if damage == "context":
            self.context = self.context.model_copy(update={"ticket_digest": "0" * 64})
        self.reader = configured_mock_budget_read(
            self.config, self.resolve_context, self.revalidate,
            transport=httpx.MockTransport(self.handle), clock=lambda: self.now,
        )
        assert self.reader is not None

    def substitute(self, req: httpx.Request) -> httpx.Response:
        self.replacement_calls += 1
        raise AssertionError("substituted transport must never be used")

    def resolve_context(self, req: GoogleBudgetHTTPTicketV1) -> GoogleBudgetHTTPContext:
        if self.damage == "transport-context":
            assert self.reader is not None
            self.reader.transport = httpx.MockTransport(self.substitute)
        return self.context

    def revalidate(self, req: GoogleBudgetHTTPTicketV1) -> None:
        assert req == ticket()
        self.revalidations += 1
        if (self.damage == "transport-authorization"
                or (self.damage == "transport-after-read" and self.calls)):
            assert self.reader is not None
            self.reader.transport = httpx.MockTransport(self.substitute)
        if self.calls and self.damage in {"source", "privacy", "revoked"}:
            raise ValueError(SECRET)
        if self.damage == "authorization-expiry" and self.calls:
            self.now += timedelta(seconds=31)
        if self.damage == "authorization-disable" and self.calls:
            self.config.customer_google_budget_http_mode = "disabled"

    def handle(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        assert req.method == "POST" and str(req.url) == ticket().account.endpoint()
        assert req.headers["authorization"] == "Bearer " + SECRET
        assert req.headers["developer-token"] == SECRET
        assert req.headers["login-customer-id"] == "9999999999"
        body = json.loads(req.content)
        kind = next(k for k, q in V24_QUERIES.items() if q == body["query"])
        cursor = body.get("pageToken")
        assert req.content.decode() == request_body(kind, cursor)
        assert set(body) <= {"query", "pageToken"}
        # Retain a real HTTP-style paginated body, including v24 query metadata.
        rows = self.source.data[kind]
        payload: dict[str, Any] = dict(results=rows, queryResourceConsumption="1")
        if kind == "campaign":
            payload["results"] = rows[:1] if cursor is None else rows[1:]
            payload["totalResultsCount"] = "2"
            if cursor is None:
                payload["nextPageToken"] = "next-page"
        headers = {"content-type": "application/json; charset=utf-8",
                   "request-id": f"mock-request-{len(self.calls)}"}
        if self.damage in {"stream-expiry", "stream-overflow"}:
            harness = self
            class Stream(httpx.SyncByteStream):
                def __iter__(self) -> Iterator[bytes]:
                    yield b" " * 131072
                    if harness.damage == "stream-expiry":
                        harness.now += timedelta(seconds=31)
                    yield b" " * 131072
                    yield b" " * 131072
                def close(self) -> None:
                    harness.stream_closed = True
            return httpx.Response(200, headers=headers, stream=Stream())
        if self.damage == "timeout":
            raise httpx.ReadTimeout(SECRET, request=req)
        if self.damage == "expiry":
            self.now += timedelta(seconds=31)
        if self.damage == "clock-rollback":
            self.now -= timedelta(seconds=1)
        if self.damage == "disabled":
            self.config.customer_google_budget_http_mode = "disabled"
        if self.damage == "redirect":
            return httpx.Response(302, headers={"location": "https://example.invalid/"})
        if self.damage == "error":
            return httpx.Response(401, content=SECRET)
        if self.damage == "request-id":
            del headers["request-id"]
        if self.damage == "repeat-request-id":
            headers["request-id"] = "same"
        if self.damage == "encoding":
            headers["content-encoding"] = "unexpected"
        if self.damage == "content-type":
            headers["content-type"] = "text/html"
        if self.damage == "oversize":
            return httpx.Response(200, headers=headers, content=b"x" * 262145)
        if self.damage == "malformed":
            return httpx.Response(200, headers=headers, content=b'{"results":[],"results":[]}')
        if self.damage == "nan":
            return httpx.Response(200, headers=headers, content=b'{"results":NaN}')
        if self.damage == "unknown":
            payload["secret"] = SECRET
        if self.damage == "total":
            payload["totalResultsCount"] = "99"
        if self.damage == "metadata":
            payload["queryResourceConsumption"] = 1
        if self.damage == "missing-false" and kind == "customer":
            del rows[0][kind]["manager"]
        if self.damage == "foreign" and kind == "customer":
            rows[0][kind]["resourceName"] = "customers/9999999999"
        if self.damage == "missing-zero" and kind == "campaignBudget":
            del rows[0][kind]["amountMicros"]
        if self.damage == "cursor-loop" and kind == "campaign":
            payload["nextPageToken"] = "next-page"
        return httpx.Response(200, headers=headers, json=payload)


def test_exact_mock_http_transcript_and_no_legacy_admission(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    h = Harness()
    assert h.reader is not None
    proof = h.reader(ticket())
    assert len(h.calls) == len(proof.pages) == 4
    assert [p.request_cursor for p in proof.pages] == [None, None, "next-page", None]
    assert proof.provenance == "mock_http" and proof.provider_authentication == "not_verified"
    assert proof.implementation == "not_assessed" and not proof.advertising_writes_enabled
    assert h.revalidations >= 2 * len(h.calls)
    for req, page in zip(h.calls, proof.pages, strict=True):
        assert sha(req.content.decode()) == page.request_body_digest
        assert sha(page.response_json) == page.response_digest
    raw = proof.model_dump_json()
    assert SECRET not in raw + repr(h.context) + h.context.model_dump_json() + caplog.text
    assert GoogleBudgetHTTPProofV1.model_validate_json(raw) == proof
    with pytest.raises(ValidationError):
        GoogleBudgetReadProofV1.model_validate_json(raw)
    original, _ = events()
    with pytest.raises(ValidationError):
        GoogleBudgetObservationV1.model_validate(
            {**original.model_dump(), "proof": json.loads(raw)}
        )


@pytest.mark.parametrize("damage", [
    "context", "timeout", "stream-expiry", "stream-overflow", "expiry", "clock-rollback",
    "disabled", "redirect", "error",
    "request-id", "repeat-request-id", "encoding", "content-type", "oversize", "malformed",
    "nan", "unknown", "total", "metadata", "missing-false", "foreign", "missing-zero",
    "cursor-loop", "source", "privacy", "revoked", "authorization-expiry", "authorization-disable",
    "transport-context", "transport-authorization", "transport-after-read",
])
def test_mock_http_refusal_and_redaction(damage: str, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    h = Harness(damage)
    assert h.reader is not None
    with pytest.raises(GoogleBudgetHTTPUnavailable) as error:
        h.reader(ticket())
    assert str(error.value) == "google_budget_http_unavailable"
    assert SECRET not in "".join(traceback.format_exception(error.value)) + caplog.text
    assert h.revalidations >= 2  # Final revalidation also occurs on failed IO.
    assert h.replacement_calls == 0
    if damage in {"transport-context", "transport-authorization"}:
        assert not h.calls
    assert len(h.calls) <= 4  # No retries, redirects or alternate endpoint.
    if damage.startswith("stream-"):
        assert h.stream_closed


@pytest.mark.parametrize(
    "damage", ["order", "endpoint", "request", "response", "deadline", "origin"],
)
def test_transcript_tampering_refuses(damage: str) -> None:
    h = Harness()
    assert h.reader is not None
    raw = h.reader(ticket()).model_dump(mode="json")
    if damage == "order":
        raw["pages"][0], raw["pages"][1] = raw["pages"][1], raw["pages"][0]
    elif damage == "endpoint":
        raw["pages"][0]["endpoint"] = "https://example.invalid/"
    elif damage == "request":
        raw["pages"][0]["request_body_digest"] = "0" * 64
    elif damage == "response":
        raw["pages"][0]["response_json"] += " "
    elif damage == "deadline":
        raw["pages"][0]["received_at"] = (NOW + timedelta(seconds=60)).isoformat()
    else:
        raw["provenance"] = "authenticated_google"
    with pytest.raises(ValidationError):
        GoogleBudgetHTTPProofV1.model_validate(raw)


def test_default_disabled_and_no_live_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INLET_CUSTOMER_GOOGLE_BUDGET_HTTP_MODE", raising=False)
    config = Settings(_env_file=None)
    assert config.customer_google_budget_http_mode == "disabled"
    def forbidden(*args: Any) -> Any:
        raise AssertionError("disabled runtime must not resolve context or transport")
    assert configured_mock_budget_read(
        config, forbidden, forbidden, transport=httpx.MockTransport(forbidden),
    ) is None
    monkeypatch.setenv("INLET_CUSTOMER_GOOGLE_BUDGET_HTTP_MODE", "live")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
    class OtherTransport(httpx.MockTransport):
        pass
    config.customer_google_budget_http_mode = "mock_http"
    with pytest.raises(ValueError, match="only explicit mock"):
        configured_mock_budget_read(
            config, forbidden, forbidden, transport=OtherTransport(forbidden)
        )
