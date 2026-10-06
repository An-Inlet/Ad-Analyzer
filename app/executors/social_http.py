"""Shared bounded HTTP mechanics; no runtime registration or mutation retries."""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from contextvars import ContextVar
from datetime import datetime
from decimal import Decimal, InvalidOperation
from time import monotonic
from typing import Any

import httpx

from app.publication.contracts import fingerprint
from app.publication.social_contracts import (
    OUTPUT_KINDS,
    ProviderMediaBinding,
    ProviderMediaReader,
    SocialBoundRequest,
    SocialProviderContext,
    SocialProviderReceipt,
    SocialProviderResponse,
    SocialResourceRef,
    SocialValidationEvidence,
    social_resource,
)

_private_http: ContextVar[bool] = ContextVar("social_private_http", default=False)


class _PrivateHTTPLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # httpx INFO logs include the request URL, including Meta appsecret_proof.
        return not _private_http.get()


logging.getLogger("httpx").addFilter(_PrivateHTTPLogFilter())


class SocialPublicationUnavailable(RuntimeError):
    """Only sanitized constant codes; no raw provider bodies, URLs or credentials."""


def resolved(request: SocialBoundRequest, ref: SocialResourceRef) -> str:
    return social_resource(request.scope, request.resources[ref.step_id], ref.kind)


def decimal_budget(micros: int) -> float:
    amount = Decimal(micros) / Decimal(1_000_000)
    result = float(amount)
    if Decimal(str(result)) != amount:
        raise SocialPublicationUnavailable("social_budget_not_representable")
    return result


def matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and matches(value, actual[key]) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(matches(a, b) for a, b in zip(expected, actual, strict=True))
        )
    if isinstance(expected, bool) or expected is None:
        return type(actual) is type(expected) and actual == expected
    if isinstance(expected, int | float):
        if isinstance(actual, bool) or not isinstance(actual, int | float | str):
            return False
        try:
            return Decimal(str(expected)) == Decimal(str(actual))
        except InvalidOperation:
            return False
    return type(actual) is type(expected) and actual == expected


def missing(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return not isinstance(actual, dict) or any(
            key not in actual or missing(value, actual[key]) for key, value in expected.items()
        )
    return False


class SocialHTTP(ABC):
    provider: str
    origin: str

    def __init__(
        self, media: ProviderMediaReader, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.media, self.transport = media, transport  # Constructors open no sockets.

    def check(
        self, request: SocialBoundRequest, context: SocialProviderContext, now: datetime
    ) -> SocialBoundRequest:
        request = SocialBoundRequest.model_validate(request.model_dump())
        if (
            request.scope != context.scope
            or request.scope.account.platform != self.provider
            or now.tzinfo is None
            or not request.dispatched_at <= now < context.expires_at
            or not context.access_token.get_secret_value()
        ):
            raise SocialPublicationUnavailable("social_context_unavailable")
        return request

    def media_bytes(self, request: SocialBoundRequest, binding: ProviderMediaBinding) -> bytes:
        try:
            raw = self.media.read_verified(request.scope.workspace_id, binding)
        except Exception:
            raise SocialPublicationUnavailable("social_media_unavailable") from None
        if (
            not isinstance(raw, bytes)
            or len(raw) != binding.byte_size
            or hashlib.sha256(raw).hexdigest() != binding.sha256
        ):
            raise SocialPublicationUnavailable("social_media_integrity_failed")
        return raw

    def send(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        *,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        form: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> dict[str, Any]:
        # Called only with compiler-selected fixed paths. Never accept an absolute URL.
        if not path.startswith("/") or ".." in path or ":" in path or "?" in path:
            raise SocialPublicationUnavailable("social_path_invalid")
        log_token = _private_http.set(True)
        deadline = monotonic() + 30
        try:
            with (
                httpx.Client(
                    transport=self.transport, timeout=12, follow_redirects=False
                ) as client,
                client.stream(
                    method,
                    self.origin + path,
                    headers={**headers, "Accept-Encoding": "identity"},
                    params=params,
                    json=body,
                    data=form,
                    files=files,
                ) as response,
            ):
                if response.headers.get("Content-Encoding", "identity") != "identity":
                    raise SocialPublicationUnavailable("social_response_invalid")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2_000_000 or monotonic() > deadline:
                        raise SocialPublicationUnavailable("social_response_invalid")
                if response.status_code != 200:
                    raise SocialPublicationUnavailable("social_provider_unavailable")
                value = json.loads(raw)
        except (httpx.HTTPError, ValueError, OSError):
            raise SocialPublicationUnavailable("social_provider_unavailable") from None
        finally:
            _private_http.reset(log_token)
        if not isinstance(value, dict) or value.get("error"):
            raise SocialPublicationUnavailable("social_response_invalid")
        return value

    @staticmethod
    def resource(request: SocialBoundRequest, external_id: Any) -> str:
        if not isinstance(external_id, str):
            raise SocialPublicationUnavailable("social_response_invalid")
        provider = "meta" if request.scope.account.platform == "meta_ads" else "tiktok"
        kind = OUTPUT_KINDS[request.step.operation.kind]
        resource = f"{provider}/{request.scope.external_advertiser_id}/{kind}/{external_id}"
        try:
            social_resource(request.scope, resource, kind)
        except ValueError:
            raise SocialPublicationUnavailable("social_response_invalid") from None
        return resource

    @staticmethod
    def receipt(
        request: SocialBoundRequest,
        now: datetime,
        outcome: str = "unknown",
        resource: str | None = None,
        expected: dict[str, Any] | None = None,
    ) -> SocialProviderReceipt:
        return SocialProviderReceipt.model_validate(
            dict(
                scope=request.scope,
                plan_id=request.plan_id,
                plan_digest=request.plan_digest,
                step_id=request.step.step_id,
                fence=request.fence,
                request_digest=request.digest(),
                outcome=outcome,
                resource_kind=OUTPUT_KINDS[request.step.operation.kind],
                resource_name=resource,
                readback_digest=fingerprint("inlet.social-readback.v1", expected)
                if expected
                else None,
                evidence={
                    "unknown": "unresolved",
                    "conflict": "mismatch",
                    "verified_effect": "exact_readback",
                }[outcome],
                observed_at=now,
            )
        )

    def verified(
        self,
        request: SocialBoundRequest,
        now: datetime,
        resource: str,
        expected: dict[str, Any],
        actual: Any,
    ) -> SocialProviderReceipt:
        if missing(expected, actual):
            return self.receipt(request, now)
        if not matches(expected, actual):
            return self.receipt(request, now, "conflict")
        return self.receipt(request, now, "verified_effect", resource, expected)

    def validate_only(
        self, request: SocialBoundRequest, context: SocialProviderContext, now: datetime
    ) -> SocialValidationEvidence:
        request = self.check(request, context, now)
        # Honest local validation only. Unsupported provider validation is not simulated.
        self.prepare(request)
        return SocialValidationEvidence(
            request_digest=request.digest(), kind="local_schema", valid=True
        )

    @abstractmethod
    def prepare(self, request: SocialBoundRequest) -> tuple[str, dict[str, Any]]: ...

    @abstractmethod
    def apply_once(
        self, request: SocialBoundRequest, context: SocialProviderContext, now: datetime
    ) -> SocialProviderResponse: ...

    @abstractmethod
    def read_back(
        self,
        request: SocialBoundRequest,
        response: SocialProviderResponse,
        context: SocialProviderContext,
        now: datetime,
    ) -> SocialProviderReceipt: ...

    def reconcile(
        self,
        request: SocialBoundRequest,
        history: list[SocialProviderResponse],
        context: SocialProviderContext,
        now: datetime,
    ) -> SocialProviderReceipt:
        request = self.check(request, context, now)
        if len(history) > 32 or any(r.request_digest != request.digest() for r in history):
            raise SocialPublicationUnavailable("social_attempt_mismatch")
        names = {r.resource_name for r in history if r.outcome == "acknowledged"}
        if len(names) > 1:
            return self.receipt(request, now, "conflict")
        if len(names) == 1 and None not in names:
            return self.read_back(
                request,
                SocialProviderResponse(
                    request_digest=request.digest(),
                    resource_name=next(iter(names)),
                    outcome="acknowledged",
                ),
                context,
                now,
            )
        # No name searches, mutation retries, or inferred authoritative absence.
        return self.receipt(request, now)
