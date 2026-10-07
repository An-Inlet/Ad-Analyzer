"""Separate status-only activation of the exact reviewed linked Push resources."""

import json
from datetime import datetime
from typing import Any, Literal

import httpx

from app.executors.social_http import SocialPublicationUnavailable, matches, missing
from app.executors.tiktok_linked_publication import LinkedPushTikTokTransport
from app.publication.activation_contracts import (
    ActivationContext,
    ActivationObservation,
    ActivationReceipt,
    ActivationRequest,
    ActivationResponse,
)
from app.publication.contracts import fingerprint
from app.publication.social_contracts import (
    ProviderMediaReader,
    SocialProviderContext,
    social_resource,
)
from app.publication.tiktok_linked_plan import (
    LINKED_OUTPUTS,
    LinkedPushAdV1,
    LinkedPushBoundRequestV1,
)


class LinkedPushTikTokActivationHTTP:
    def __init__(self, media: ProviderMediaReader, *, transport: httpx.MockTransport) -> None:
        self.http = LinkedPushTikTokTransport(media, transport=transport)

    def check(
        self, request: ActivationRequest, context: ActivationContext, now: datetime
    ) -> tuple[LinkedPushBoundRequestV1, SocialProviderContext]:
        request = ActivationRequest.model_validate_json(request.model_dump_json())
        original = request.target.original_request
        if (
            not isinstance(original, LinkedPushBoundRequestV1)
            or context.account != request.account
            or now.tzinfo is None
            or now < request.dispatched_at
            or original.step.operation.kind
            not in {
                "tiktok_linked_push_campaign",
                "tiktok_linked_push_adgroup",
                "tiktok_linked_push_ad",
            }
        ):
            raise SocialPublicationUnavailable("linked_activation_scope_mismatch")
        converted = SocialProviderContext(
            scope=original.scope, access_token=context.access_token, expires_at=context.expires_at
        )
        self.http.check(original, converted, now)
        social_resource(
            original.scope,
            request.target.resource_name,
            LINKED_OUTPUTS[original.step.operation.kind],
        )
        return original, converted

    def read_exact(
        self,
        request: ActivationRequest,
        context: ActivationContext,
        expected: Literal["paused", "active"],
        now: datetime,
    ) -> ActivationObservation:
        original, converted = self.check(request, context, now)
        kind = {
            "tiktok_linked_push_campaign": "campaign",
            "tiktok_linked_push_adgroup": "adgroup",
            "tiktok_linked_push_ad": "ad",
        }[original.step.operation.kind]
        external = social_resource(
            original.scope,
            request.target.resource_name,
            LINKED_OUTPUTS[original.step.operation.kind],
        )
        _, wanted = self.http.prepare(original)
        if isinstance(original.step.operation, LinkedPushAdV1):
            wanted = {
                "advertiser_id": wanted["advertiser_id"],
                "adgroup_id": wanted["adgroup_id"],
                **wanted["creatives"][0],
            }
        wanted[kind + "_id"] = external
        wanted["operation_status"] = (
            request.target.before_status if expected == "paused" else request.target.target_status
        )
        actual = None
        try:
            data = self.http.data(
                self.http.send(
                    "GET",
                    f"/open_api/v1.3/{kind}/get/",
                    {"Access-Token": converted.access_token.get_secret_value()},
                    params={
                        "advertiser_id": original.scope.external_advertiser_id,
                        "filtering": json.dumps({kind + "_ids": [external]}),
                        "fields": json.dumps(sorted(wanted)),
                        "page": "1",
                        "page_size": "100",
                    },
                )
            )
            rows = data.get("list") if isinstance(data, dict) else None
            if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict):
                actual = rows[0]
        except SocialPublicationUnavailable:
            pass
        state: Literal["paused", "active", "unknown", "conflict"] = "unknown"
        digest = None
        if not missing(wanted, actual):
            if matches(wanted, actual):
                if (
                    isinstance(original.step.operation, LinkedPushAdV1)
                    and original.review.configuration.identity.identity_type == "TT_USER"
                    and isinstance(actual, dict)
                    and actual.get("identity_authorized_bc_id") not in (None, "")
                ):
                    state = "conflict"
                else:
                    state, digest = expected, fingerprint("inlet.linked-tiktok-readback.v1", wanted)
            elif not (
                expected == "active"
                and matches({**wanted, "operation_status": request.target.before_status}, actual)
            ):
                state = "conflict"
        return ActivationObservation(
            request_digest=request.digest(),
            resource_name=request.target.resource_name,
            state=state,
            readback_digest=digest,
            observed_at=now,
        )

    def apply_once(
        self, request: ActivationRequest, context: ActivationContext, now: datetime
    ) -> ActivationResponse:
        original, converted = self.check(request, context, now)
        observed = self.read_exact(request, context, "paused", now)
        if (
            observed.state != "paused"
            or observed.readback_digest != request.target.before_readback_digest
        ):
            raise SocialPublicationUnavailable("linked_activation_preflight_changed")
        kind = {
            "tiktok_linked_push_campaign": "campaign",
            "tiktok_linked_push_adgroup": "adgroup",
            "tiktok_linked_push_ad": "ad",
        }[original.step.operation.kind]
        external = social_resource(
            original.scope,
            request.target.resource_name,
            LINKED_OUTPUTS[original.step.operation.kind],
        )
        body: dict[str, Any] = {
            "advertiser_id": original.scope.external_advertiser_id,
            kind + "_ids": [external],
            "operation_status": request.target.target_status,
        }
        if kind == "adgroup":
            body["allow_partial_success"] = False
        try:
            self.http.data(
                self.http.send(
                    "POST",
                    f"/open_api/v1.3/{kind}/status/update/",
                    {"Access-Token": converted.access_token.get_secret_value()},
                    body=body,
                )
            )
            outcome: Literal["acknowledged", "unknown"] = "acknowledged"
        except SocialPublicationUnavailable:
            outcome = "unknown"
        return ActivationResponse(request_digest=request.digest(), outcome=outcome)

    def read_back(
        self,
        request: ActivationRequest,
        response: ActivationResponse,
        context: ActivationContext,
        now: datetime,
    ) -> ActivationReceipt:
        if response.request_digest != request.digest():
            raise SocialPublicationUnavailable("linked_activation_attempt_mismatch")
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
            raise SocialPublicationUnavailable("linked_activation_attempt_mismatch")
        return self.read_back(
            request,
            ActivationResponse(request_digest=request.digest(), outcome="unknown"),
            context,
            now,
        )
