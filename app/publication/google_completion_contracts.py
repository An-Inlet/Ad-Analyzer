"""Original synchronous response capture, never request finality or financial proof."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import Environment, ExecutionAccount
from app.publication.optimization_contracts import OptimizationRequest, OptimizationResponse
from app.publication.provider_contracts import Digest, Id


class GoogleSynchronousCapture(StrictModel):
    profile: Literal["google.v25.single_update.synchronous_response.v1"] = (
        "google.v25.single_update.synchronous_response.v1"
    )
    account: ExecutionAccount
    environment: Environment
    request_digest: Digest
    attempt_id: Id
    fence: Id
    endpoint: Literal["campaignBudgets:mutate", "campaigns:mutate"]
    resource_name: str = Field(
        pattern=r"^customers/[0-9]{10}/(?:campaignBudgets|campaigns)/[0-9]+$", max_length=160
    )
    operation_digest: Digest
    response_digest: Digest
    operation_count: Literal[1] = 1
    partial_failure: Literal[False] = False
    validate_only: Literal[False] = False
    assertion: Literal["original_configuration_operation_completed"] = (
        "original_configuration_operation_completed"
    )

    @model_validator(mode="after")
    def native_scope(self) -> "GoogleSynchronousCapture":
        collection = "campaignBudgets" if self.endpoint == "campaignBudgets:mutate" else "campaigns"
        if self.account.account.platform != "google_ads" or not self.resource_name.startswith(
            f"customers/{self.account.external_advertiser_id}/{collection}/"
        ):
            raise ValueError("original Google response scope mismatch")
        return self

    def bind(self, request: OptimizationRequest) -> None:
        # Local import avoids the executor/contract import cycle. This pure method emits no IO.
        from app.executors.google_optimization import GoogleOptimizationTransport

        endpoint, resource, operation = GoogleOptimizationTransport.operation(request)
        if (
            self.account != request.intent.scope
            or self.account.account.platform != "google_ads"
            or self.environment != request.intent.mandate.environment
            or self.request_digest != request.digest()
            or self.attempt_id != request.attempt_id
            or self.fence != request.fence
            or self.endpoint != endpoint
            or self.resource_name != resource
            or self.operation_digest != fingerprint("inlet.google-original-operation.v1", operation)
            or self.response_digest
            != fingerprint(
                "inlet.google-original-result.v1", {"results": [{"resourceName": resource}]}
            )
        ):
            raise ValueError("original Google response binding changed")


class GoogleCapturedResponse(OptimizationResponse):
    # Separate in-process transport channel: shared response JSON/digests stay unchanged.
    capture: GoogleSynchronousCapture = Field(exclude=True, repr=False)


class GoogleCompletionDocument(StrictModel):
    schema_version: Literal["inlet.google-original-completion.v1"] = (
        "inlet.google-original-completion.v1"
    )
    capture: GoogleSynchronousCapture
    recorded_at: AwareDatetime

    def bind(self, request: OptimizationRequest, now: datetime) -> None:
        self.capture.bind(request)
        if not request.dispatched_at <= self.recorded_at <= now:
            raise ValueError("original Google response time changed")

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))
