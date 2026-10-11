"""Caller-owned SQL traffic reads; no identity/provider IO, commits or runtime factory."""

from typing import Annotated, Literal

from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.presence_models import MetricPresenceRow
from app.campaign_performance.presence_storage import read_presence
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.range_receipts import read_range_receipt
from app.campaign_performance.service import manifest
from app.lifecycle.privacy import workspace_export_revision
from app.planning_documents.common import Frozen
from app.planning_documents.context import AccountRef
from app.planning_documents.evidence_local import changed
from app.planning_documents.selected_plan_contracts import (
    SelectedCampaignBindingV1,
    SelectedPlanPinV1,
)
from app.planning_documents.selected_plan_reader import load_selected_plan_graph
from app.planning_documents.selected_traffic import PROFILE, RawRangeTrafficGraphV1
from app.planning_documents.selected_traffic_contracts import SelectedTrafficPinV1
from app.planning_documents.source_contracts import SourceFence
from app.publication import customer_intents
from app.publication.contracts import fingerprint

GapReason = Literal["range_traffic_provenance_unavailable", "unsupported_traffic_profile"]
EXPLANATIONS: dict[str, str] = {
    "range_traffic_provenance_unavailable": (
        "Raw requested-range traffic provenance is unavailable."
    ),
    "unsupported_traffic_profile": "This reporting source has no supported raw traffic profile.",
}


class KnownTrafficGap(Frozen):
    schema_version: Literal["inlet.selected-traffic-gap.v1"] = "inlet.selected-traffic-gap.v1"
    account: AccountRef
    selected_pin: SelectedPlanPinV1
    reason: GapReason
    explanation: Annotated[str, Field(strict=True, min_length=1, max_length=160)]

    @model_validator(mode="after")
    def binding(self) -> "KnownTrafficGap":
        if (
            self.account != self.selected_pin.account
            or self.explanation != EXPLANATIONS[self.reason]
        ):
            raise ValueError("traffic gap binding mismatch")
        return self


def _clean(db: Session) -> None:
    if (
        db.get_transaction() is None
        or db.in_nested_transaction()
        or db.new
        or db.dirty
        or db.deleted
    ):
        raise changed()


def _gap(account: AccountRef, pin: SelectedPlanPinV1, reason: GapReason) -> KnownTrafficGap:
    return KnownTrafficGap(
        account=account, selected_pin=pin, reason=reason, explanation=EXPLANATIONS[reason]
    )


def _source(db: Session, account: AccountRef) -> SourceFence:
    scope = customer_intents.account(db, account.workspace_id, account.account_id)
    ref = AccountRef(
        workspace_id=scope.workspace_id,
        account_id=scope.account.account_id,
        connection_id=scope.account.connection_id,
        platform=scope.account.platform,
        connection_version=scope.connection_version,
    )
    if ref != account:
        raise changed()
    return SourceFence(
        account=ref,
        source_binding_digest=fingerprint(
            "inlet.planning-source.v1", scope.model_dump(mode="json")
        ),
        source_revision=scope.connection_version,
        privacy_revision=workspace_export_revision(db, ref.workspace_id),
    )


def load_raw_range_traffic(
    db: Session,
    *,
    account: AccountRef,
    expected_source: SourceFence,
    selected_pin: SelectedPlanPinV1,
) -> RawRangeTrafficGraphV1 | KnownTrafficGap:
    """Caller authorizes original session before/after; absence never skips selected validation."""
    try:
        _clean(db)
        account = AccountRef.model_validate(account)
        source = SourceFence.model_validate(expected_source)
        pin = SelectedPlanPinV1.model_validate(selected_pin)
        with db.no_autoflush:
            if source.account != account or _source(db, account) != source:
                raise changed()
            selected = load_selected_plan_graph(
                db, account=account, expected_source=source, capture_id=pin.capture_id
            )
            if selected.pin() != pin:
                raise changed()
            if account.platform != "google_ads":
                return _gap(account, pin, "unsupported_traffic_profile")
            completion = db.get(
                PerformanceCompletion, pin.aggregate.completion_id, populate_existing=True
            )
            if completion is None:
                raise changed()
            present = read_presence(db, completion)
            if present is not None and present[0].producer_contract != PROFILE:
                raise changed()
            ids = db.scalars(
                select(RangeReceiptRow.request_id)
                .where(
                    RangeReceiptRow.workspace_id == account.workspace_id,
                    RangeReceiptRow.account_id == account.account_id,
                    RangeReceiptRow.completion_id == pin.aggregate.completion_id,
                )
                .limit(2)
            ).all()
            if len(ids) > 1:
                raise changed()
            if not ids:
                return _gap(account, pin, "range_traffic_provenance_unavailable")
            receipt = read_range_receipt(db, account.workspace_id, account.account_id, ids[0])
            # Validate exact parent even before a legitimate missing-sidecar gap.
            if (
                receipt.final_scope != pin.aggregate.scope
                or receipt.manifest_digest != pin.aggregate.manifest_digest
                or receipt.requested_starts_on != pin.aggregate.starts_on
                or receipt.requested_ends_on != pin.aggregate.ends_on
            ):
                raise changed()
            if present is None:
                return _gap(account, pin, "range_traffic_provenance_unavailable")
            header, facts = present
            if header.producer_contract != PROFILE:
                raise changed()  # Unknown present provenance is not a convenient absence.
            graph = RawRangeTrafficGraphV1(
                receipt=receipt,
                header=header,
                facts=facts,
                campaigns=selected.campaigns,
                source_fence=source,
            )
            traffic = graph.pin()
            if (
                traffic.aggregate != pin.aggregate
                or traffic.campaign_map_digest != pin.campaign_map_digest
            ):
                raise changed()
            owned = db.get(AdvertisingAccount, account.account_id, populate_existing=True)
            if owned is None:
                raise changed()
            digest, rows = manifest(
                db, owned, receipt.requested_starts_on, receipt.requested_ends_on
            )
            actual = {
                (x.campaign_id, x.metric_date): (x.impressions, x.clicks, x.cost_micros)
                for x in rows
            }
            observed = {
                (x.campaign_id, x.metric_date): (
                    x.impressions.value,
                    x.clicks.value,
                    x.spend_micros.value,
                )
                for x in facts
            }
            if digest != receipt.manifest_digest or len(actual) != len(rows) or actual != observed:
                raise changed()
            return graph
    except (ValueError, KeyError, TypeError):
        raise changed() from None


def validate_historical_raw_range_traffic(
    db: Session, *, expected_pin: SelectedTrafficPinV1
) -> None:
    """Pin-only immutable historical validation, never current source qualification."""
    try:
        _clean(db)
        pin = SelectedTrafficPinV1.model_validate(expected_pin)
        account = pin.source_fence.account
        with db.no_autoflush:
            owned = db.get(AdvertisingAccount, account.account_id, populate_existing=True)
            if owned is None or (owned.workspace_id, owned.platform.value) != (
                account.workspace_id,
                account.platform,
            ):
                raise changed()
            receipt = read_range_receipt(
                db,
                account.workspace_id,
                account.account_id,
                pin.range_request_id,
                require_current=False,
            )
            completion = db.get(
                PerformanceCompletion, receipt.completion_id, populate_existing=True
            )
            if completion is None:
                raise changed()
            present = read_presence(db, completion)
            if present is None:
                raise changed()
            header, facts = present
            rows = db.execute(
                select(Campaign.id, Campaign.external_campaign_id)
                .join(MetricPresenceRow, MetricPresenceRow.campaign_id == Campaign.id)
                .where(
                    MetricPresenceRow.completion_id == receipt.completion_id,
                    Campaign.account_id == account.account_id,
                    Campaign.platform == account.platform,
                )
                .distinct()
                .order_by(Campaign.id)
                .limit(10_001)
            ).all()
            if len(rows) > 10_000:
                raise changed()
            graph = RawRangeTrafficGraphV1(
                receipt=receipt,
                header=header,
                facts=facts,
                campaigns=tuple(
                    SelectedCampaignBindingV1(
                        campaign_id=x.id, native_campaign_id=x.external_campaign_id
                    )
                    for x in rows
                ),
                source_fence=pin.source_fence,
            )
            # The complete original map is not stored separately. Its saved digest
            # remains opaque; validate every retained fact's ownership, not today's full map.
            if graph.pin().model_dump(exclude={"campaign_map_digest"}) != pin.model_dump(
                exclude={"campaign_map_digest"}
            ):
                raise changed()
    except (ValueError, KeyError, TypeError):
        raise changed() from None
