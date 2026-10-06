"""Frozen workspace-only lifecycle v1; no implicit identity or provider mutation scope."""

from typing import Literal

from pydantic import Field

from app.goals.schemas import StrictModel


class LifecycleScopeV1(StrictModel):
    schema_version: Literal["inlet.lifecycle.scope.v1"] = "inlet.lifecycle.scope.v1"
    kind: Literal["workspace"] = "workspace"
    workspace_id: int = Field(strict=True, gt=0)


class LifecycleInputV1(StrictModel):
    schema_version: Literal["inlet.lifecycle.request.v1"] = "inlet.lifecycle.request.v1"
    scope: LifecycleScopeV1
    operation: Literal["export", "close"]
    # No client-supplied disposition, completion, actor, provider-verification or purge flag.


class LifecycleBlockerV1(StrictModel):
    code: Literal[
        "publication_unresolved",
        "billing_unresolved",
        "provider_revocation_unverified",
        "worker_not_quiescent",
        "retention_policy_unset",
        "media_generation_unavailable",
        "legacy_scope_unclassified",
        "export_incomplete",
    ]
    subsystem: str = Field(pattern=r"^[a-z_]{1,48}$")
    resolution_kind: Literal[
        "implementation", "customer_action", "operator_evidence", "owner_policy"
    ]
