"""Separate exact activation of a fully verified, customer-reviewed paused graph.

Status observation is not delivery or treatment time. No activation is inherited from
creation consent; adapters accept only these fixed, digest-bound status transitions.
"""

from datetime import datetime
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, SecretStr, model_validator

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.coordinator_contracts import CreationRequest
from app.publication.execution_contracts import ExecutionAccount, ProviderMandateBinding
from app.publication.provider_contracts import Digest, Id

ACTIVATABLE = {
    "tiktok_linked_push_campaign": "campaigns",
    "tiktok_linked_push_adgroup": "adgroups",
    "tiktok_linked_push_ad": "ads",
    "google_create_paused_campaign": "campaigns",
    "google_create_paused_ad_group": "adGroups",
    "google_create_exact_keyword": "adGroupCriteria",
    "google_create_paused_responsive_search_ad": "adGroupAds",
    "meta_create_paused_campaign": "campaigns",
    "meta_create_paused_adset": "adsets",
    "meta_create_paused_ad": "ads",
    "tiktok_create_disabled_campaign": "campaigns",
    "tiktok_create_disabled_adgroup": "adgroups",
    "tiktok_create_disabled_video_ad": "ads",
}


class ActivationTarget(StrictModel):
    source_attempt_id: Id
    source_receipt_id: Id
    source_receipt_digest: Digest
    original_request: CreationRequest
    resource_name: str = Field(min_length=1, max_length=384)
    before_readback_digest: Digest
    before_status: Literal["PAUSED", "DISABLE"]
    target_status: Literal["ENABLED", "ACTIVE", "ENABLE"]

    @model_validator(mode="after")
    def exact(self) -> "ActivationTarget":
        original = self.original_request
        provider = original.scope.account.platform
        expected_kind = ACTIVATABLE.get(original.step.operation.kind)
        family = "customers" if provider == "google_ads" else provider.removesuffix("_ads")
        before, after = {
            "google_ads": ("PAUSED", "ENABLED"),
            "meta_ads": ("PAUSED", "ACTIVE"),
            "tiktok_ads": ("DISABLE", "ENABLE"),
        }[provider]
        prefix = f"{family}/{original.scope.external_advertiser_id}/{expected_kind}/"
        suffix = self.resource_name.removeprefix(prefix)
        import re

        if (
            expected_kind is None
            or not self.resource_name.startswith(prefix)
            or not re.fullmatch(
                r"[0-9]+~[0-9]+"
                if expected_kind in {"adGroupCriteria", "adGroupAds"}
                else r"[0-9]+",
                suffix,
            )
            or (self.before_status, self.target_status) != (before, after)
        ):
            raise ValueError("unsupported or foreign exact activation target")
        return self

    @property
    def step_id(self) -> str:
        return self.original_request.step.step_id


class ActivationPlan(StrictModel):
    schema_version: Literal["inlet.activation-plan.v1"] = "inlet.activation-plan.v1"
    account: ExecutionAccount
    parent_run_id: Id
    parent_plan_digest: Digest
    targets: list[ActivationTarget] = Field(min_length=2, max_length=96)
    external_compare_and_swap: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def bound_graph(self) -> "ActivationPlan":
        if (
            len({t.step_id for t in self.targets}) != len(self.targets)
            or len({t.resource_name for t in self.targets}) != len(self.targets)
            or any(
                ExecutionAccount.from_publication(t.original_request.scope) != self.account
                or t.original_request.plan_id != self.parent_run_id
                or t.original_request.plan_digest != self.parent_plan_digest
                for t in self.targets
            )
            or ACTIVATABLE[self.targets[-1].original_request.step.operation.kind]
            not in {"campaigns"}
            or sum(
                ACTIVATABLE[t.original_request.step.operation.kind] in {"campaigns"}
                for t in self.targets
            )
            != 1
        ):
            raise ValueError("exact graph with campaign activated last required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class ActivationRequest(StrictModel):
    run_id: Id
    plan_digest: Digest
    review_digest: Digest
    mandate: ProviderMandateBinding
    target: ActivationTarget
    fence: Id
    dispatched_at: AwareDatetime

    @property
    def account(self) -> ExecutionAccount:
        return ExecutionAccount.from_publication(self.target.original_request.scope)

    def digest(self) -> str:
        return fingerprint("inlet.activation-request.v1", self.model_dump(mode="json"))


class ActivationContext(StrictModel):
    account: ExecutionAccount
    access_token: SecretStr = Field(exclude=True, repr=False)
    developer_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    app_secret: SecretStr | None = Field(default=None, exclude=True, repr=False)
    login_customer_id: str | None = Field(default=None, pattern=r"^[0-9]{10}$")
    expires_at: AwareDatetime


class ActivationObservation(StrictModel):
    request_digest: Digest
    resource_name: str = Field(min_length=1, max_length=384)
    state: Literal["paused", "active", "unknown", "conflict"]
    readback_digest: Digest | None
    observed_at: AwareDatetime
    provider_compare_and_swap: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def proof(self) -> "ActivationObservation":
        if (self.state in {"paused", "active"}) != (self.readback_digest is not None):
            raise ValueError("exact status requires complete reviewed readback")
        return self


class ActivationResponse(StrictModel):
    request_digest: Digest
    outcome: Literal["acknowledged", "unknown"]


class ActivationReceipt(StrictModel):
    run_id: Id
    step_id: str = Field(min_length=1, max_length=32)
    account: ExecutionAccount
    fence: Id
    request_digest: Digest
    outcome: Literal["verified_target_state", "unknown", "conflict", "verified_no_effect"]
    evidence: Literal["exact_readback", "unresolved", "mismatch", "authoritative_no_effect"]
    resource_name: str | None = Field(default=None, max_length=384)
    readback_digest: Digest | None = None
    observed_at: AwareDatetime
    effective_time_evidence: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def proof(self) -> "ActivationReceipt":
        verified = self.outcome == "verified_target_state"
        if (verified and (self.resource_name is None or self.readback_digest is None)) or (
            not verified and (self.resource_name is not None or self.readback_digest is not None)
        ):
            raise ValueError("activation state requires exact readback")
        if (
            self.evidence
            != {
                "verified_target_state": "exact_readback",
                "unknown": "unresolved",
                "conflict": "mismatch",
                "verified_no_effect": "authoritative_no_effect",
            }[self.outcome]
        ):
            raise ValueError("activation receipt evidence mismatch")
        return self


class ActivationTransport(Protocol):
    def read_exact(
        self,
        request: ActivationRequest,
        context: ActivationContext,
        expected: Literal["paused", "active"],
        now: datetime,
    ) -> ActivationObservation: ...
    def apply_once(
        self, request: ActivationRequest, context: ActivationContext, now: datetime
    ) -> ActivationResponse: ...
    def read_back(
        self,
        request: ActivationRequest,
        response: ActivationResponse,
        context: ActivationContext,
        now: datetime,
    ) -> ActivationReceipt: ...
    def reconcile(
        self,
        request: ActivationRequest,
        history: list[ActivationResponse],
        context: ActivationContext,
        now: datetime,
    ) -> ActivationReceipt: ...


def get_activation_transport() -> ActivationTransport | None:
    return None
