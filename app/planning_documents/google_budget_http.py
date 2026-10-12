"""Bounded search-only HTTP protocol, qualified only with an explicit MockTransport."""

from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic

import httpx
from pydantic import AwareDatetime, Field, SecretStr

from app.executors.social_http import _private_http
from app.planning_documents.common import Digest, Frozen
from app.planning_documents.google_budget_http_proof import (
    V24_QUERIES,
    GoogleBudgetHTTPPageV1,
    GoogleBudgetHTTPProofV1,
    GoogleBudgetHTTPTicketV1,
    decoded,
    request_body,
    sha,
)
from app.planning_documents.google_budget_owner_contracts import _instant
from app.planning_documents.google_budget_read import MAX_PROOF_BYTES
from app.settings import Settings


class GoogleBudgetHTTPContext(Frozen):
    ticket_digest: Digest
    expires_at: AwareDatetime
    access_token: SecretStr = Field(exclude=True, repr=False)
    developer_token: SecretStr = Field(exclude=True, repr=False)
    login_customer_id: str | None = Field(
        default=None, strict=True, pattern=r"^[0-9]{10}$", exclude=True, repr=False,
    )


class GoogleBudgetHTTPUnavailable(RuntimeError):
    """Fixed failure; never retain a request, credential or provider error body."""


class GoogleBudgetHTTPRead:
    def __init__(
        self,
        context_reader: Callable[[GoogleBudgetHTTPTicketV1], GoogleBudgetHTTPContext],
        revalidate: Callable[[GoogleBudgetHTTPTicketV1], None],
        *,
        transport: httpx.MockTransport,
        enabled: Callable[[], bool],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if type(transport) is not httpx.MockTransport:
            raise ValueError("only explicit mock HTTP qualification is available")
        self.context_reader, self.revalidate = context_reader, revalidate
        self.transport, self.enabled, self.clock = transport, enabled, clock

    def __call__(self, ticket: GoogleBudgetHTTPTicketV1) -> GoogleBudgetHTTPProofV1:
        private = _private_http.set(True)
        try:
            req = GoogleBudgetHTTPTicketV1.model_validate(ticket)
            try:
                return self._capture(req)
            except Exception:
                # Failed IO/context/parsing must not bypass current source/privacy checks.
                self.revalidate(req)
                raise
        except Exception:
            raise GoogleBudgetHTTPUnavailable("google_budget_http_unavailable") from None
        finally:
            _private_http.reset(private)

    def _capture(self, req: GoogleBudgetHTTPTicketV1) -> GoogleBudgetHTTPProofV1:
        transport = self.transport
        deadline = monotonic() + 60
        last = req.prepared_at
        expires = req.expires_at

        def time_check() -> datetime:
            nonlocal last
            now = _instant(self.clock())
            if not last <= now < expires or monotonic() >= deadline:
                raise ValueError("original acquisition deadline elapsed")
            last = now
            return now

        def check() -> datetime:
            if (self.enabled() is not True or type(transport) is not httpx.MockTransport
                    or self.transport is not transport):
                raise ValueError("runtime disabled or non-mock transport")
            time_check()
            self.revalidate(req)
            now = time_check()
            if (self.enabled() is not True or self.transport is not transport
                    or type(transport) is not httpx.MockTransport):
                raise ValueError("runtime changed during authorization")
            return now

        check()
        context = GoogleBudgetHTTPContext.model_validate(self.context_reader(req))
        if (context.ticket_digest != req.digest() or not context.access_token.get_secret_value()
                or not context.developer_token.get_secret_value()):
            raise ValueError("credential context does not bind original ticket")
        expires = min(expires, _instant(context.expires_at))
        check()
        headers = {
            "Authorization": "Bearer " + context.access_token.get_secret_value(),
            "developer-token": context.developer_token.get_secret_value(),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        }
        if context.login_customer_id is not None:
            headers["login-customer-id"] = context.login_customer_id
        pages: list[GoogleBudgetHTTPPageV1] = []
        total_bytes = 0
        with httpx.Client(
            transport=transport, timeout=httpx.Timeout(12, connect=5),
            follow_redirects=False, trust_env=False,
        ) as client:
            for kind in V24_QUERIES:
                cursor: str | None = None
                seen: set[str] = set()
                resources: set[str] = set()
                for _ in range(10):
                    started = check()
                    body = request_body(kind, cursor)
                    raw = bytearray()
                    try:
                        with client.stream(
                            "POST", req.account.endpoint(), headers=headers,
                            content=body.encode("utf-8"),
                        ) as response:
                            ids = response.headers.get_list("request-id")
                            if (response.status_code != 200 or len(ids) != 1
                                    or response.headers.get("content-type", "")
                                    .split(";")[0].strip()
                                    != "application/json"
                                    or response.headers.get("content-encoding", "identity")
                                    != "identity"):
                                raise ValueError("HTTP response not admitted")
                            for chunk in response.iter_bytes():
                                time_check()
                                total_bytes += len(chunk)
                                if (len(raw) + len(chunk) > 262144
                                        or total_bytes > MAX_PROOF_BYTES - 32768):
                                    raise ValueError("HTTP response capacity")
                                raw.extend(chunk)
                    finally:
                        check()
                    ended = check()
                    value = raw.decode("utf-8")
                    page = GoogleBudgetHTTPPageV1(
                        query_kind=kind, request_cursor=cursor, requested_at=started,
                        received_at=ended, response_json=value, endpoint=req.account.endpoint(),
                        request_body_digest=sha(body), response_digest=sha(value),
                        request_id=ids[0],
                    )
                    rows, cursor, _ = decoded(page, req.account.native_customer_id)
                    names = {r["resourceName"] for r in rows}
                    if len(names) != len(rows) or names & resources:
                        raise ValueError("duplicate resource")
                    resources.update(names)
                    if len(resources) > 200 or (cursor is not None and cursor in seen):
                        raise ValueError("pagination capacity or loop")
                    pages.append(page)
                    if cursor is None:
                        break
                    seen.add(cursor)
                else:
                    raise ValueError("terminal response missing")
            proof = GoogleBudgetHTTPProofV1(ticket=req, pages=tuple(pages))
            check()
            return proof


def configured_mock_budget_read(
    config: Settings,
    context_reader: Callable[[GoogleBudgetHTTPTicketV1], GoogleBudgetHTTPContext],
    revalidate: Callable[[GoogleBudgetHTTPTicketV1], None],
    *,
    transport: httpx.MockTransport,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> GoogleBudgetHTTPRead | None:
    """Offline composition only. No settings secret, vault, token refresh or live factory."""
    if config.customer_google_budget_http_mode != "mock_http":
        return None
    return GoogleBudgetHTTPRead(
        context_reader, revalidate, transport=transport,
        enabled=lambda: config.customer_google_budget_http_mode == "mock_http", clock=clock,
    )
