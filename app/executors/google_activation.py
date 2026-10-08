"""Fixed Google v25 status-only activation with full reviewed-field readback.

No retry, delivery-time inference, or compare-and-swap claim. Factory is disabled.
"""

from datetime import datetime
from typing import Literal

import httpx

from app import advertising_capabilities
from app.executors.google_publication import (
    GooglePublicationHTTP,
    GooglePublicationUnavailable,
    _fields,
    _matches,
    serialize,
)
from app.publication.activation_contracts import (
    ActivationContext,
    ActivationObservation,
    ActivationReceipt,
    ActivationRequest,
    ActivationResponse,
)
from app.publication.contracts import fingerprint
from app.publication.google_execution_completion_contracts import (
    GoogleCapturedActivationResponse,
    capture_success,
)
from app.publication.provider_contracts import BoundProviderRequest, ProviderContext


class GoogleActivationHTTP:
    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self.http = GooglePublicationHTTP(transport=transport)

    def check(
        self, request: ActivationRequest, context: ActivationContext, now: datetime
    ) -> tuple[BoundProviderRequest, ProviderContext]:
        request = ActivationRequest.model_validate(request.model_dump())
        original = request.target.original_request
        if not isinstance(original, BoundProviderRequest) or context.account != request.account:
            raise GooglePublicationUnavailable("google_activation_scope_mismatch")
        converted = ProviderContext(
            scope=original.scope,
            login_customer_id=context.login_customer_id,
            access_token=context.access_token,
            developer_token=context.developer_token,
            expires_at=context.expires_at,
        )
        self.http._check(original, converted, now)
        return original, converted

    def read_exact(
        self,
        request: ActivationRequest,
        context: ActivationContext,
        expected: Literal["paused", "active"],
        now: datetime,
    ) -> ActivationObservation:
        original, converted = self.check(request, context, now)
        collection, table, operation = serialize(original)
        resource = self.http._resource_name(original, collection, request.target.resource_name)
        wanted = dict(operation["create"])
        wanted["resourceName"] = resource
        wanted["status"] = (
            request.target.before_status if expected == "paused" else request.target.target_status
        )
        if "manualCpc" in wanted:
            wanted.pop("manualCpc")
            wanted["biddingStrategyType"] = "MANUAL_CPC"
        fields = _fields(wanted, table)
        query = (
            f"SELECT {', '.join(fields)} FROM {table} "
            f"WHERE {table}.resource_name = '{resource}' LIMIT 2"
        )
        state: Literal["paused", "active", "unknown", "conflict"] = "unknown"
        digest = None
        try:
            data = self.http._post(original, converted, "googleAds:search", {"query": query})
            rows = data.get("results")
            if isinstance(rows, list) and len(rows) == 1 and not data.get("nextPageToken"):
                key = table.split("_")[0] + "".join(p.title() for p in table.split("_")[1:])
                actual = rows[0].get(key) if isinstance(rows[0], dict) else None
                if _matches(wanted, actual):
                    state, digest = expected, fingerprint("google.readback.v25", wanted)
                else:
                    state = "conflict"
                    # Old paused state may precede a delayed original activation. It is
                    # neither authoritative no-effect nor permission to submit again.
                    old = {**wanted, "status": request.target.before_status}
                    if expected == "active" and _matches(old, actual):
                        state = "unknown"
        except GooglePublicationUnavailable:
            pass
        return ActivationObservation(
            request_digest=request.digest(),
            resource_name=resource,
            state=state,
            readback_digest=digest,
            observed_at=now,
        )

    def apply_once(
        self, request: ActivationRequest, context: ActivationContext, now: datetime
    ) -> ActivationResponse:
        advertising_capabilities.require_advertising_write()
        original, converted = self.check(request, context, now)
        before = self.read_exact(request, context, "paused", now)
        if (
            before.state != "paused"
            or before.readback_digest != request.target.before_readback_digest
        ):
            raise GooglePublicationUnavailable("google_activation_preflight_changed")
        collection = serialize(original)[0]
        try:
            data = self.http._post(
                original,
                converted,
                f"{collection}:mutate",
                {
                    "operations": [
                        {
                            "update": {
                                "resourceName": request.target.resource_name,
                                "status": request.target.target_status,
                            },
                            "updateMask": "status",
                        }
                    ],
                    "partialFailure": False,
                    "validateOnly": False,
                },
            )
            rows = data.get("results")
            if (
                not isinstance(rows, list)
                or len(rows) != 1
                or not isinstance(rows[0], dict)
                or rows[0].get("resourceName") != request.target.resource_name
            ):
                raise GooglePublicationUnavailable("google_activation_acknowledgement_invalid")
            return GoogleCapturedActivationResponse(
                request_digest=request.digest(),
                outcome="acknowledged",
                capture=capture_success(request, data),
            )
        except (GooglePublicationUnavailable, ValueError):
            return ActivationResponse(request_digest=request.digest(), outcome="unknown")

    def read_back(
        self,
        request: ActivationRequest,
        response: ActivationResponse,
        context: ActivationContext,
        now: datetime,
    ) -> ActivationReceipt:
        if response.request_digest != request.digest():
            raise GooglePublicationUnavailable("google_activation_attempt_mismatch")
        observed = self.read_exact(request, context, "active", now)
        outcome: Literal["verified_target_state", "unknown", "conflict"] = (
            "verified_target_state"
            if observed.state == "active"
            else "conflict"
            if observed.state == "conflict"
            else "unknown"
        )
        return ActivationReceipt(
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

    def reconcile(
        self,
        request: ActivationRequest,
        history: list[ActivationResponse],
        context: ActivationContext,
        now: datetime,
    ) -> ActivationReceipt:
        if any(r.request_digest != request.digest() for r in history):
            raise GooglePublicationUnavailable("google_activation_attempt_mismatch")
        return self.read_back(
            request,
            ActivationResponse(request_digest=request.digest(), outcome="unknown"),
            context,
            now,
        )
