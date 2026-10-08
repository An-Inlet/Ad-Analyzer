"""Common bounded optimization IO. Models are evidence, never coordinator authority."""

import hashlib
import hmac
import json
import re
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from functools import wraps
from time import monotonic
from typing import Any

import httpx

from app.executors import planning_reads
from app.executors.social_http import SocialPublicationUnavailable, _private_http
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import (
    MetaBudgetSetV1,
    MetaStatusSetV1,
    OptimizationContext,
    OptimizationReceipt,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationState,
    OptimizationValidation,
    TikTokBudgetSetV1,
    TikTokStatusSetV1,
)


class OptimizationUnavailable(RuntimeError):
    pass


def validated_read[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    @wraps(fn)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except (ValueError, KeyError, TypeError, AttributeError):
            raise OptimizationUnavailable("optimization_state_unavailable") from None

    return wrapped


def micros(value: Any, exponent: int, *, minor: bool = False) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise OptimizationUnavailable("optimization_money_invalid")
    try:
        amount = Decimal(str(value)) * (10 ** (6 - exponent) if minor else 1_000_000)
        if (
            not amount.is_finite()
            or amount != amount.to_integral_value()
            or not 0 <= amount <= 10**15
        ):
            raise ValueError
        result = int(amount)
        if result % 10 ** (6 - exponent):
            raise ValueError
        return result
    except (ValueError, ArithmeticError):
        raise OptimizationUnavailable("optimization_money_invalid") from None


class OptimizationHTTP:
    provider: str
    origin: str

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def check(self, scope: ExecutionAccount, context: OptimizationContext, now: datetime) -> None:
        if (
            scope != context.scope
            or scope.account.platform != self.provider
            or not re.fullmatch(r"[0-9]{1,32}", scope.external_advertiser_id)
            or now.tzinfo is None
            or now >= context.expires_at
            or not context.access_token.get_secret_value()
        ):
            raise OptimizationUnavailable("optimization_context_invalid")

    def send(
        self,
        method: str,
        path: str,
        context: OptimizationContext,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        planning_reads.social_read(self.provider, method, path, params=params, body=body)
        if not re.fullmatch(r"/[A-Za-z0-9_./]+", path) or ".." in path:
            raise OptimizationUnavailable("optimization_path_invalid")
        token = context.access_token.get_secret_value()
        headers = {"Accept-Encoding": "identity"}
        query = dict(params or {})
        form = None
        if self.provider == "meta_ads":
            headers["Authorization"] = "Bearer " + token
            if body is not None:
                form = {k: str(v) for k, v in body.items()}
            if context.app_secret:
                proof = hmac.new(
                    context.app_secret.get_secret_value().encode(), token.encode(), hashlib.sha256
                ).hexdigest()
                if form is not None:
                    form["appsecret_proof"] = proof
                else:
                    query["appsecret_proof"] = proof
        else:
            headers["Access-Token"] = token
        privacy = _private_http.set(True)
        deadline = monotonic() + 30
        try:
            with (
                httpx.Client(
                    transport=self.transport, timeout=12, follow_redirects=False
                ) as client,
                client.stream(
                    method,
                    self.origin + path,
                    headers=headers,
                    params=query,
                    data=form,
                    json=body if self.provider == "tiktok_ads" else None,
                ) as response,
            ):
                if (
                    response.status_code != 200
                    or response.headers.get("Content-Encoding", "identity") != "identity"
                ):
                    raise OptimizationUnavailable("optimization_provider_unavailable")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2_000_000 or monotonic() > deadline:
                        raise OptimizationUnavailable("optimization_response_invalid")
                data = json.loads(raw)
            if not isinstance(data, dict) or data.get("error"):
                raise ValueError
            if self.provider == "tiktok_ads":
                if (
                    type(data.get("code")) is not int
                    or data["code"] != 0
                    or not isinstance(data.get("data"), dict)
                ):
                    raise ValueError
                return dict(data["data"])
            return data
        except (httpx.HTTPError, ValueError, OSError):
            raise OptimizationUnavailable("optimization_provider_unavailable") from None
        finally:
            _private_http.reset(privacy)

    def blockers(self, request: OptimizationRequest, now: datetime) -> list[str]:
        s, e, a = request.before, request.exposure, request.intent.action
        blockers = list(s.unsupported_features)
        if not s.complete or any(
            v is not False
            for v in (s.sharing_enabled, s.schedule_adjustments_enabled, s.rebalance_enabled)
        ):
            blockers.append("incomplete_or_unsupported_topology")
        if (
            e.portfolio_upper_micros is None
            or not e.observed_at <= now < e.expires_at
            or e.qualification_id != s.qualification_id
        ):
            blockers.append("qualified_exposure_required")
        if e.environment == "live":
            blockers.append("native_profile_and_exposure_unqualified")
        if not request.dispatched_at <= now or (now - s.observed_at).total_seconds() > 300:
            blockers.append("stale_preflight")
        if isinstance(a, MetaBudgetSetV1):
            value = getattr(s, a.budget_field + "_micros", None)
            if value is None or value <= 0:
                blockers.append("budget_mode_change_unavailable")
        if isinstance(a, TikTokBudgetSetV1) and getattr(s, "budget_micros", None) is None:
            blockers.append("budget_unavailable")
        return sorted(set(blockers))[:32]

    def validate_only(
        self, request: OptimizationRequest, context: OptimizationContext, now: datetime
    ) -> OptimizationValidation:
        request = OptimizationRequest.model_validate(request.model_dump())
        self.check(request.intent.scope, context, now)
        blockers = self.blockers(request, now)
        return OptimizationValidation(
            request_digest=request.digest(),
            kind="unsupported" if blockers else "local_schema",
            valid=not blockers,
            blockers=blockers,
        )

    def receipt(
        self,
        request: OptimizationRequest,
        now: datetime,
        outcome: str = "unknown",
        after: OptimizationState | None = None,
    ) -> OptimizationReceipt:
        return OptimizationReceipt.model_validate(
            dict(
                action_id=request.action_id,
                attempt_id=request.attempt_id,
                fence=request.fence,
                scope=request.intent.scope,
                mandate=request.intent.mandate,
                intent_digest=request.intent_digest,
                request_digest=request.digest(),
                budget_owner_key=request.intent.budget_owner.key(request.intent.scope),
                before_state_digest=request.before.digest(),
                after=after,
                outcome=outcome,
                evidence={
                    "unknown": "unresolved",
                    "conflict": "mismatch",
                    "verified_target_state": "exact_readback",
                }[outcome],
                observed_at=now,
            )
        )

    def compare(
        self, request: OptimizationRequest, after: OptimizationState, now: datetime
    ) -> OptimizationReceipt:
        before = request.before
        a = request.intent.action
        updates: dict[str, Any] = {}
        if isinstance(a, MetaBudgetSetV1):
            updates[a.budget_field + "_micros"] = a.amount_micros
        elif isinstance(a, TikTokBudgetSetV1):
            updates["budget_micros"] = a.amount_micros
        elif isinstance(a, MetaStatusSetV1 | TikTokStatusSetV1):
            updates["configured_status"] = (
                a.status if isinstance(a, MetaStatusSetV1) else a.operation_status
            )
            # Delivery/review/parent constraints are not activation evidence.
            updates["effective_status"] = after.effective_status
            if before.target.kind == "campaign":
                updates["parent_configured_status"] = updates["configured_status"]
        wanted = before.model_copy(update=updates)
        if after.digest() == wanted.digest():
            return self.receipt(request, now, "verified_target_state", after)
        if after.digest() == before.digest():
            return self.receipt(request, now)  # An external writer may have reverted an effect.
        return self.receipt(request, now, "conflict")

    def read_current(self, *args: Any, **kwargs: Any) -> OptimizationState:
        raise NotImplementedError

    def read_back(
        self,
        request: OptimizationRequest,
        response: OptimizationResponse,
        context: OptimizationContext,
        now: datetime,
    ) -> OptimizationReceipt:
        request = OptimizationRequest.model_validate(request.model_dump())
        self.check(request.intent.scope, context, now)
        if response.request_digest != request.digest():
            raise OptimizationUnavailable("optimization_attempt_mismatch")
        try:
            state = self.read_current(
                request.intent.scope,
                request.intent.target,
                request.before.money,
                request.intent.qualification_id,
                request.intent.qualification_revision,
                context,
                now,
            )
            return self.compare(request, state, now)
        except (
            OptimizationUnavailable,
            SocialPublicationUnavailable,
            ValueError,
            KeyError,
            TypeError,
        ):
            return self.receipt(request, now)

    def reconcile(
        self,
        request: OptimizationRequest,
        history: list[OptimizationResponse],
        context: OptimizationContext,
        now: datetime,
    ) -> OptimizationReceipt:
        if (
            not history
            or len(history) > 32
            or any(r.request_digest != request.digest() for r in history)
        ):
            raise OptimizationUnavailable("optimization_attempt_mismatch")
        return self.read_back(request, history[-1], context, now)
