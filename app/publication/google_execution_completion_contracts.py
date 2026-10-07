"""Original Google synchronous operation evidence; never financial or delivery finality."""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.publication.activation_contracts import ActivationRequest, ActivationResponse
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import Environment, ExecutionAccount, Purpose
from app.publication.google_completion_contracts import GoogleCompletionDocument
from app.publication.provider_contracts import BoundProviderRequest, Digest, Id, ProviderResponse

GoogleExecutionRequest = BoundProviderRequest | ActivationRequest
Endpoint = Literal[
    "campaignBudgets:mutate",
    "campaigns:mutate",
    "conversionGoalCampaignConfigs:mutate",
    "campaignCriteria:mutate",
    "adGroups:mutate",
    "adGroupCriteria:mutate",
    "adGroupAds:mutate",
]


def operation(request: GoogleExecutionRequest) -> tuple[str, dict[str, Any]]:
    from app.executors.google_publication import serialize

    if isinstance(request, BoundProviderRequest):
        collection, _, body = serialize(request)
    else:
        original = request.target.original_request
        if not isinstance(original, BoundProviderRequest):
            raise ValueError("Google original request required")
        collection = serialize(original)[0]
        if collection not in {"campaigns", "adGroups", "adGroupCriteria", "adGroupAds"}:
            raise ValueError("unsupported activation collection")
        body = {
            "update": {
                "resourceName": request.target.resource_name,
                "status": request.target.target_status,
            },
            "updateMask": "status",
        }
    return collection + ":mutate", body


def account_for(request: GoogleExecutionRequest) -> ExecutionAccount:
    return (
        ExecutionAccount.from_publication(request.scope)
        if isinstance(request, BoundProviderRequest)
        else request.account
    )


def validate_resource(request: GoogleExecutionRequest, resource: str) -> None:
    endpoint, body = operation(request)
    collection = endpoint.split(":")[0]
    prefix = f"customers/{account_for(request).external_advertiser_id}/{collection}/"
    composite = collection in {"campaignCriteria", "adGroupCriteria", "adGroupAds"}
    if not re.fullmatch(
        re.escape(prefix) + (r"[0-9]+~[0-9]+" if composite else r"[0-9]+"), resource
    ):
        raise ValueError("Google original result scope changed")
    if "update" in body and resource != body["update"]["resourceName"]:
        raise ValueError("Google original update result changed")
    if composite and "create" in body:
        parent = body["create"].get("campaign", body["create"].get("adGroup"))
        if (
            not isinstance(parent, str)
            or resource.rsplit("/", 1)[1].split("~")[0] != parent.rsplit("/", 1)[1]
        ):
            raise ValueError("Google original result parent changed")


class GoogleExecutionCaptureV2(StrictModel):
    profile: Literal["google.v25.single_resource_mutate.synchronous_response.v2"] = (
        "google.v25.single_resource_mutate.synchronous_response.v2"
    )
    purpose: Literal["create_paused", "activate"]
    account: ExecutionAccount
    request_digest: Digest
    fence: Id
    endpoint: Endpoint
    resource_name: str = Field(min_length=1, max_length=256)
    operation_digest: Digest
    response_digest: Digest
    partial_failure: Literal["false", "unsupported"]
    operation_count: Literal[1] = 1
    validate_only: Literal[False] = False
    assertion: Literal["original_configuration_operation_completed"] = (
        "original_configuration_operation_completed"
    )

    @model_validator(mode="after")
    def scope(self) -> "GoogleExecutionCaptureV2":
        collection = self.endpoint.split(":")[0]
        if (
            self.account.account.platform != "google_ads"
            or not self.resource_name.startswith(
                f"customers/{self.account.external_advertiser_id}/{collection}/"
            )
            or self.partial_failure
            != ("unsupported" if collection == "conversionGoalCampaignConfigs" else "false")
        ):
            raise ValueError("Google capture scope or service mode changed")
        return self

    def bind(self, request: GoogleExecutionRequest) -> None:
        GoogleExecutionCaptureV2.model_validate(self.model_dump())
        endpoint, body = operation(request)
        validate_resource(request, self.resource_name)
        if (
            self.account != account_for(request)
            or self.fence != request.fence
            or self.request_digest != request.digest()
            or self.endpoint != endpoint
            or self.purpose
            != ("create_paused" if isinstance(request, BoundProviderRequest) else "activate")
            or self.operation_digest != fingerprint("inlet.google-original-operation.v2", body)
            or self.response_digest
            != fingerprint(
                "inlet.google-original-result.v2",
                {"results": [{"resourceName": self.resource_name}]},
            )
        ):
            raise ValueError("Google original capture binding changed")


def capture_success(
    request: GoogleExecutionRequest, data: dict[str, Any]
) -> GoogleExecutionCaptureV2:
    # Exact default resource-name response. Unknown/extra envelopes are not normalized away.
    if (
        set(data) != {"results"}
        or not isinstance(data["results"], list)
        or len(data["results"]) != 1
    ):
        raise ValueError("exact synchronous original result required")
    row = data["results"][0]
    if (
        not isinstance(row, dict)
        or set(row) != {"resourceName"}
        or not isinstance(row["resourceName"], str)
    ):
        raise ValueError("exact synchronous original resource required")
    endpoint, body = operation(request)
    capture = GoogleExecutionCaptureV2.model_validate(
        {
            "purpose": "create_paused" if isinstance(request, BoundProviderRequest) else "activate",
            "account": account_for(request),
            "request_digest": request.digest(),
            "fence": request.fence,
            "endpoint": endpoint,
            "resource_name": row["resourceName"],
            "operation_digest": fingerprint("inlet.google-original-operation.v2", body),
            "response_digest": fingerprint("inlet.google-original-result.v2", data),
            "partial_failure": "unsupported"
            if endpoint == "conversionGoalCampaignConfigs:mutate"
            else "false",
        }
    )
    capture.bind(request)
    return capture


class GoogleCapturedCreationResponse(ProviderResponse):
    capture: GoogleExecutionCaptureV2 = Field(exclude=True, repr=False)


class GoogleCapturedActivationResponse(ActivationResponse):
    capture: GoogleExecutionCaptureV2 = Field(exclude=True, repr=False)


class GoogleExecutionCompletionV2(StrictModel):
    schema_version: Literal["inlet.google-original-completion.v2"] = (
        "inlet.google-original-completion.v2"
    )
    capture: GoogleExecutionCaptureV2
    environment: Environment
    attempt_id: Id
    run_id: Id
    step_id: str = Field(min_length=1, max_length=32)
    normalized_response_digest: Digest
    recorded_at: AwareDatetime

    def bind(self, request: GoogleExecutionRequest, now: datetime) -> None:
        self.capture.bind(request)
        if isinstance(request, BoundProviderRequest):
            run, step = request.plan_id, request.step.step_id
            response = ProviderResponse(
                request_digest=request.digest(),
                outcome="acknowledged",
                resource_name=self.capture.resource_name,
            )
            response_digest = fingerprint(
                "inlet.provider-response.v1", response.model_dump(mode="json")
            )
        else:
            run, step = request.run_id, request.target.step_id
            if self.environment != request.mandate.environment:
                raise ValueError("Google original execution environment changed")
            activation_response = ActivationResponse(
                request_digest=request.digest(), outcome="acknowledged"
            )
            response_digest = fingerprint(
                "inlet.activation-response.v1", activation_response.model_dump(mode="json")
            )
        if (
            self.run_id != run
            or self.step_id != step
            or self.normalized_response_digest != response_digest
            or not request.dispatched_at <= self.recorded_at <= now
        ):
            raise ValueError("Google original execution lineage changed")

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


def parse_completion(value: object) -> GoogleCompletionDocument | GoogleExecutionCompletionV2:
    if (
        isinstance(value, dict)
        and value.get("schema_version") == "inlet.google-original-completion.v2"
    ):
        return GoogleExecutionCompletionV2.model_validate(value)
    return GoogleCompletionDocument.model_validate(value)


class OriginalOperationCompletionView(StrictModel):
    status: Literal["completed", "unavailable"] = "unavailable"
    purpose: Purpose | None = None
    profile: (
        Literal[
            "google.v25.single_update.synchronous_response.v1",
            "google.v25.single_resource_mutate.synchronous_response.v2",
        ]
        | None
    ) = None
    commitment: Digest | None = None
    assertion: Literal["original_configuration_operation_only"] = (
        "original_configuration_operation_only"
    )
    financial_finality: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def complete(self) -> "OriginalOperationCompletionView":
        if (
            self.status == "completed"
            and any(v is None for v in (self.purpose, self.profile, self.commitment))
        ) or (
            self.status == "unavailable"
            and any(v is not None for v in (self.purpose, self.profile, self.commitment))
        ):
            raise ValueError("exact completion projection required")
        if self.status == "completed" and (
            (self.purpose == "existing_campaign_optimize")
            != (self.profile == "google.v25.single_update.synchronous_response.v1")
        ):
            raise ValueError("completion purpose and profile mismatch")
        return self
