"""Retained v4 commitments; historical opaque values are not reconstructed facts."""

from typing import Annotated

from pydantic import Field, model_validator

from app.planning_documents.common import Digest, Frozen, Id, fingerprint
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.selected_plan_contracts import SelectedPlanPinV1
from app.planning_documents.source_contracts import SourceFence


class SelectedHeadProofV1(Frozen):
    selection_id: Id
    selection_digest: Digest
    invalidated: Annotated[bool, Field(strict=True)]


class SelectedRetainedAccountProofV1(Frozen):
    source_fence: SourceFence
    # Retained opaque commitment to the then-current mutable aggregate state.
    # Historical validation checks its binding, not reconstruction of old SQL rows.
    legacy_reporting_digest: Digest
    selection_head: SelectedHeadProofV1 | None
    capture_pin: SelectedPlanPinV1 | None

    @model_validator(mode="after")
    def binding(self) -> "SelectedRetainedAccountProofV1":
        fence = self.source_fence
        if fence.source_revision != fence.account.connection_version:
            raise ValueError("retained source version mismatch")
        pin, head = self.capture_pin, self.selection_head
        if pin is not None and (
            pin.source_fence != fence
            or head is None
            or head.invalidated
            or (head.selection_id, head.selection_digest)
            != (pin.selection_id, pin.selection_digest)
        ):
            raise ValueError("retained selected pin must match its active original head")
        return self

    def state_digest(self) -> str:
        value = type(self).model_validate(self)
        return fingerprint("inlet.local-reporting-state.v3", value.model_dump(mode="json"))


class SelectedRetainedProofV1(Frozen):
    accounts: tuple[SelectedRetainedAccountProofV1, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique(self) -> "SelectedRetainedProofV1":
        ids = tuple(item.source_fence.account.account_id for item in self.accounts)
        if len(set(ids)) != len(ids) or ids != tuple(sorted(ids)):
            raise ValueError("unique ordered retained account proofs required")
        return self

    def assert_inputs(self, inputs: PlanInputRevision, privacy_revision: int) -> None:
        self = type(self).model_validate(self)
        inputs = PlanInputRevision.model_validate(inputs)
        if inputs.selected_reporting is None:
            raise ValueError("v4 requires an explicit selected capture input tuple")
        accounts = {item.source_fence.account for item in self.accounts}
        if accounts != set(inputs.accounts) or any(
            item.source_fence.privacy_revision != privacy_revision for item in self.accounts
        ):
            raise ValueError("exact retained account and privacy coverage required")
        expected = {item.account_id: item.capture_id for item in inputs.selected_reporting}
        actual = {
            item.source_fence.account.account_id: item.capture_pin.capture_id
            for item in self.accounts
            if item.capture_pin is not None
        }
        if expected != actual:
            raise ValueError("retained capture pins must match persisted input selectors")
