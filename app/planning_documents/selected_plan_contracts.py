"""Immutable selected planning commitments shared with retained documents."""

from typing import Any

from pydantic import SerializerFunctionWrapHandler, model_serializer, model_validator

from app.campaign_performance.presence_contracts import NativeId
from app.campaign_performance.selected_contracts import AggregateDependencyV1
from app.planning_documents.common import Digest, Frozen, Id, Positive
from app.planning_documents.context import AccountRef
from app.planning_documents.selected_observation_provenance import SelectedObservationProvenanceV1
from app.planning_documents.source_contracts import SourceFence


class SelectedCampaignBindingV1(Frozen):
    campaign_id: Positive
    native_campaign_id: NativeId


class SelectedPlanPinV1(Frozen):
    account: AccountRef
    source_fence: SourceFence
    aggregate: AggregateDependencyV1
    selection_id: Id
    selection_digest: Digest
    capture_id: Id
    request_digest: Digest
    capture_digest: Digest
    campaign_map_digest: Digest
    observation_provenance: SelectedObservationProvenanceV1 | None = None

    @model_serializer(mode="wrap")
    def omit_absent_provenance(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        result: dict[str, Any] = handler(self)
        if self.observation_provenance is None:
            result.pop("observation_provenance", None)
        return result

    @model_validator(mode="after")
    def scope(self) -> "SelectedPlanPinV1":
        account, scope, source = self.account, self.aggregate.scope, self.source_fence
        if (
            source.account != account
            or source.source_revision != account.connection_version
            or source.privacy_revision != scope.privacy_revision
            or (account.workspace_id, account.connection_id, account.account_id, account.platform)
            != (scope.workspace_id, scope.connection_id, scope.account_id, scope.platform)
        ):
            raise ValueError("selected plan pin scope mismatch")
        if self.observation_provenance is not None:
            self.observation_provenance.assert_aggregate(self.aggregate)
        return self
