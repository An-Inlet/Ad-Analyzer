"""Atomic raw-cell provenance. Never infer presence from normalized SQL defaults."""

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import Campaign
from app.campaign_performance.presence_contracts import (
    MAX_FACTS,
    AttributionBasisV1,
    CountCellV1,
    IntegerCountCellV1,
    MoneyCellV1,
    ReportedMetricPresenceV1,
    ReportingSemanticsV1,
    SelectedEventV1,
    presence_digest,
)
from app.campaign_performance.presence_storage import store_presence
from app.campaign_performance.range_receipt_contracts import RangeReceiptV1
from app.google_connections.range_http import GoogleAggregateRangeV1

PRODUCER = "google.v24.campaign-day.raw-required-traffic.v1"


def store_raw_range_traffic(
    db: Session,
    *,
    receipt: RangeReceiptV1,
    result: GoogleAggregateRangeV1,
    campaign_mapping: Mapping[str, int],
) -> None:
    """Caller owns authorization and the encompassing publication transaction."""
    receipt = RangeReceiptV1.model_validate(receipt)
    result = GoogleAggregateRangeV1.model_validate(result)
    request = result.request
    if (
        request.base.scope != receipt.original_scope
        or request.requested_starts_on != receipt.requested_starts_on
        or request.requested_ends_on != receipt.requested_ends_on
        or result.digest() != receipt.acquisition_digest
        or set(campaign_mapping) != {x.native_campaign_id for x in result.campaigns}
        or len(set(campaign_mapping.values())) != len(campaign_mapping)
        or any(type(x) is not int or x <= 0 for x in campaign_mapping.values())
    ):
        raise ValueError("raw traffic acquisition binding mismatch")
    scope = receipt.final_scope
    owned = {
        native: local
        for native, local in db.execute(
            select(Campaign.external_campaign_id, Campaign.id)
            .where(Campaign.account_id == scope.account_id, Campaign.platform == scope.platform)
            .limit(MAX_FACTS + 1)
        ).all()
    }
    if len(owned) > MAX_FACTS or any(
        owned.get(native) != local for native, local in campaign_mapping.items()
    ):
        raise ValueError("raw traffic campaign mapping is not owned")
    facts = tuple(
        sorted(
            (
                ReportedMetricPresenceV1(
                    completion_id=receipt.completion_id,
                    workspace_id=scope.workspace_id,
                    account_id=scope.account_id,
                    campaign_id=campaign_mapping[row.native_campaign_id],
                    native_campaign_id=row.native_campaign_id,
                    metric_date=row.metric_date,
                    impressions=IntegerCountCellV1(presence="present", value=row.impressions),
                    clicks=IntegerCountCellV1(presence="present", value=row.clicks),
                    spend_micros=MoneyCellV1(presence="present", value=row.cost_micros),
                    selected_conversions=CountCellV1(presence="unsupported", value=None),
                    selected_value_micros=MoneyCellV1(presence="unsupported", value=None),
                )
                for row in result.metrics
            ),
            key=lambda x: (x.campaign_id, x.metric_date),
        )
    )
    header = ReportingSemanticsV1(
        **scope.model_dump(exclude={"native_account_id"}),
        completion_id=receipt.completion_id,
        legacy_manifest_digest=receipt.manifest_digest,
        producer_contract=PRODUCER,
        query_descriptor=receipt.query_version,
        requested_starts_on=receipt.requested_starts_on,
        requested_ends_on=receipt.requested_ends_on,
        actual_starts_on=receipt.requested_starts_on,
        actual_ends_on=receipt.requested_ends_on,
        selected_event=SelectedEventV1(provenance="generic", native_event_id=None, label=None),
        attribution=AttributionBasisV1(
            click_window_days=None,
            view_window_days=None,
            report_time_basis="unknown",
            provenance="provider_default_unknown",
            producer_contract=PRODUCER,
        ),
        pagination_complete=True,
        closed_requested_period=True,
        completed_at=receipt.completed_at,
        fact_count=len(facts),
        fact_digest=presence_digest(facts),
    )
    store_presence(db, header, facts)
