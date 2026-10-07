"""Exact Meta status-only activation; separate DB approval remains mandatory."""

from datetime import datetime
from typing import Any, Literal

import httpx

from app.executors.meta_publication import MetaPublicationTransport
from app.executors.social_http import SocialPublicationUnavailable, matches, missing, resolved
from app.executors.tiktok_publication import TikTokPublicationTransport
from app.publication.activation_contracts import (
    ActivationContext,
    ActivationObservation,
    ActivationReceipt,
    ActivationRequest,
    ActivationResponse,
)
from app.publication.contracts import fingerprint
from app.publication.social_contracts import (
    OUTPUT_KINDS,
    MetaCreatePausedAd,
    MetaCreatePausedAdSet,
    ProviderMediaReader,
    SocialBoundRequest,
    SocialProviderContext,
    social_resource,
)


class MetaActivationHTTP:
    provider = "meta_ads"
    http: MetaPublicationTransport | TikTokPublicationTransport

    def __init__(
        self, media: ProviderMediaReader, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.http = MetaPublicationTransport(media, transport=transport)

    def check(
        self, request: ActivationRequest, context: ActivationContext, now: datetime
    ) -> tuple[SocialBoundRequest, SocialProviderContext]:
        request = ActivationRequest.model_validate(request.model_dump())
        original = request.target.original_request
        if (
            not isinstance(original, SocialBoundRequest)
            or context.account != request.account
            or request.account.account.platform != self.provider
            or now.tzinfo is None
            or now < request.dispatched_at
        ):
            raise SocialPublicationUnavailable("social_activation_scope_mismatch")
        converted = SocialProviderContext(
            scope=original.scope,
            access_token=context.access_token,
            app_secret=context.app_secret,
            expires_at=context.expires_at,
        )
        self.http.check(original, converted, now)
        social_resource(
            original.scope, request.target.resource_name, OUTPUT_KINDS[original.step.operation.kind]
        )
        return original, converted

    def observation(
        self,
        request: ActivationRequest,
        expected: Literal["paused", "active"],
        wanted: dict[str, Any],
        actual: Any,
        status_field: str,
        now: datetime,
    ) -> ActivationObservation:
        state: Literal["paused", "active", "unknown", "conflict"] = "unknown"
        digest = None
        if not missing(wanted, actual):
            if matches(wanted, actual):
                state = expected
                digest = fingerprint("inlet.social-readback.v1", wanted)
            elif expected == "active" and matches(
                {**wanted, status_field: request.target.before_status}, actual
            ):
                pass  # Paused may precede a delayed original mutation; never no-effect.
            else:
                state = "conflict"
        return ActivationObservation(
            request_digest=request.digest(),
            resource_name=request.target.resource_name,
            state=state,
            readback_digest=digest,
            observed_at=now,
        )

    def read_exact(
        self,
        request: ActivationRequest,
        context: ActivationContext,
        expected: Literal["paused", "active"],
        now: datetime,
    ) -> ActivationObservation:
        original, converted = self.check(request, context, now)
        external = social_resource(
            original.scope, request.target.resource_name, OUTPUT_KINDS[original.step.operation.kind]
        )
        _, wanted = self.http.prepare(original)
        wanted.update(
            id=external,
            account_id=original.scope.external_advertiser_id,
            status=request.target.before_status
            if expected == "paused"
            else request.target.target_status,
        )
        if isinstance(original.step.operation, MetaCreatePausedAd):
            wanted["creative"] = {"id": resolved(original, original.step.operation.creative)}
        headers, params = MetaPublicationTransport.auth(converted)
        params["fields"] = ",".join(wanted)
        actual = None
        try:
            actual = self.http.send(
                "GET", f"/{original.api_version}/{external}", headers, params=params
            )
            if isinstance(original.step.operation, MetaCreatePausedAdSet):
                actual = dict(actual)
                for key in ("start_time", "end_time"):
                    if isinstance(actual.get(key), str):
                        try:
                            observed = datetime.fromisoformat(actual[key])
                            if observed.tzinfo is not None and observed == datetime.fromisoformat(
                                wanted[key]
                            ):
                                actual[key] = wanted[key]
                        except ValueError:
                            pass
        except SocialPublicationUnavailable:
            pass
        return self.observation(request, expected, wanted, actual, "status", now)

    def apply_once(
        self, request: ActivationRequest, context: ActivationContext, now: datetime
    ) -> ActivationResponse:
        original, converted = self.check(request, context, now)
        observed = self.read_exact(request, context, "paused", now)
        if (
            observed.state != "paused"
            or observed.readback_digest != request.target.before_readback_digest
        ):
            raise SocialPublicationUnavailable("social_activation_preflight_changed")
        external = social_resource(
            original.scope, request.target.resource_name, OUTPUT_KINDS[original.step.operation.kind]
        )
        headers, proof = MetaPublicationTransport.auth(converted)
        try:
            result = self.http.send(
                "POST",
                f"/{original.api_version}/{external}",
                headers,
                form={"status": request.target.target_status, **proof},
            )
            outcome = "acknowledged" if result.get("success") is True else "unknown"
        except SocialPublicationUnavailable:
            outcome = "unknown"
        return ActivationResponse.model_validate(
            {"request_digest": request.digest(), "outcome": outcome}
        )

    def read_back(
        self,
        request: ActivationRequest,
        response: ActivationResponse,
        context: ActivationContext,
        now: datetime,
    ) -> ActivationReceipt:
        if response.request_digest != request.digest():
            raise SocialPublicationUnavailable("social_activation_attempt_mismatch")
        observed = self.read_exact(request, context, "active", now)
        outcome = (
            "verified_target_state"
            if observed.state == "active"
            else "conflict"
            if observed.state == "conflict"
            else "unknown"
        )
        return ActivationReceipt.model_validate(
            dict(
                run_id=request.run_id,
                step_id=request.target.step_id,
                account=request.account,
                fence=request.fence,
                request_digest=request.digest(),
                outcome=outcome,
                evidence={
                    "verified_target_state": "exact_readback",
                    "unknown": "unresolved",
                    "conflict": "mismatch",
                }[outcome],
                resource_name=request.target.resource_name
                if outcome == "verified_target_state"
                else None,
                readback_digest=observed.readback_digest,
                observed_at=now,
            )
        )

    def reconcile(
        self,
        request: ActivationRequest,
        history: list[ActivationResponse],
        context: ActivationContext,
        now: datetime,
    ) -> ActivationReceipt:
        if len(history) > 32 or any(r.request_digest != request.digest() for r in history):
            raise SocialPublicationUnavailable("social_activation_attempt_mismatch")
        return self.read_back(
            request,
            ActivationResponse(request_digest=request.digest(), outcome="unknown"),
            context,
            now,
        )
