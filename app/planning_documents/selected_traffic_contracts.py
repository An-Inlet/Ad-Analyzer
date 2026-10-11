"""Dependency-light raw traffic pin; DTO construction conveys no read authority."""

from typing import Literal

from pydantic import model_validator

from app.campaign_performance.presence_contracts import Digest, Frozen, Id
from app.campaign_performance.selected_contracts import AggregateDependencyV1
from app.planning_documents.source_contracts import SourceFence

TrafficProfile = Literal["google.v24.campaign-day.raw-required-traffic.v1"]


class SelectedTrafficPinV1(Frozen):
    source_fence: SourceFence
    aggregate: AggregateDependencyV1
    range_request_id: Id
    range_receipt_digest: Digest
    presence_header_digest: Digest
    presence_fact_digest: Digest
    campaign_map_digest: Digest
    producer_contract: TrafficProfile = "google.v24.campaign-day.raw-required-traffic.v1"

    @model_validator(mode="after")
    def scope(self) -> "SelectedTrafficPinV1":
        source, scope = self.source_fence, self.aggregate.scope
        account = source.account
        if (
            source.source_revision != account.connection_version
            or source.privacy_revision != scope.privacy_revision
            or (account.workspace_id, account.account_id, account.connection_id, account.platform)
            != (scope.workspace_id, scope.account_id, scope.connection_id, scope.platform)
            or scope.platform != "google_ads"
        ):
            raise ValueError("traffic source scope mismatch")
        return self
