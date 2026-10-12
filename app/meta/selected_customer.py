"""Customer-owned count-only Meta choices over a reviewed imported basis."""

import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException
from pydantic import AwareDatetime, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.automation.catalog import AutomationControlKey
from app.automation.service import AutomationControlService
from app.billing.entitlements import paid_work
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_contracts import (
    Digest,
    Frozen,
    Id,
    Positive,
    _canonical,
    _date,
)
from app.campaign_performance.selected_contracts import (
    AggregateDependencyV1,
    CustomerEventSelectionV1,
    ReportingScopeV1,
    SelectedCaptureRequestV1,
    SelectedCaptureV1,
    selection_digest,
)
from app.campaign_performance.selected_models import CurrentEventSelectionRow, SelectedCaptureRow
from app.campaign_performance.selected_storage import (
    _aggregate,
    current_scope,
    invalidate_selected_account,
    lock_scope,
    read_selected_capture,
    read_selection,
    store_selection,
)
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerSession
from app.google_connections.selected_acquisition import CaptureView
from app.google_connections.selected_customer import (
    AccountIntent,
    InvalidationIntent,
    SelectionIntent,
)
from app.meta.models import MetaConnection
from app.meta.security import Vault
from app.meta.selected_acquisition import acquire_selected
from app.meta.selected_profile import (
    EVENT,
    PRODUCER,
    query_profile_digest,
)
from app.meta.selected_profile import (
    settings as count_settings,
)
from app.planning_documents.read_context import PlanningReadContexts
from app.settings import Settings

LABEL = "Website Purchases — Count Only"


class BasisIntent(AccountIntent):
    basis_digest: Digest
    starts_on: date
    ends_on: date
    _dates = field_validator("starts_on", "ends_on", mode="before")(_date)


class MetaSelectionIntent(SelectionIntent):
    basis_digest: Digest
    starts_on: date
    ends_on: date
    _dates = field_validator("starts_on", "ends_on", mode="before")(_date)


class MetaCapturePrepareIntent(InvalidationIntent):
    basis_digest: Digest
    request_nonce: Id
    starts_on: date
    ends_on: date
    _dates = field_validator("starts_on", "ends_on", mode="before")(_date)


class MetaCaptureIntent(MetaCapturePrepareIntent):
    request_id: Id


class AvailableRangeIntent(AccountIntent):
    request_id: Id
    requested_starts_on: date
    requested_ends_on: date
    _dates = field_validator("requested_starts_on", "requested_ends_on", mode="before")(_date)


class AvailableRangeView(Frozen):
    account_id: Positive
    request_id: Id
    basis_digest: Digest
    completion_id: Id
    requested_starts_on: date
    requested_ends_on: date
    imported_starts_on: date
    imported_ends_on: date
    time_zone: str
    state: Literal["available"] = "available"
    spending_authorized: Literal[False] = False


class MetaOptionView(Frozen):
    option_id: Digest
    label: Literal["Website Purchases — Count Only"] = "Website Purchases — Count Only"
    metric_family: Literal["actions"] = "actions"
    api_version: Literal["v26.0"] = "v26.0"
    native_event: Literal["offsite_conversion.fb_pixel_purchase"] = (
        "offsite_conversion.fb_pixel_purchase"
    )


class MetaOptionsView(Frozen):
    account_id: Positive
    basis_digest: Digest
    options: tuple[MetaOptionView, ...] = Field(min_length=1, max_length=1)
    spending_authorized: Literal[False] = False


class MetaSelectionView(Frozen):
    account_id: Positive
    state: Literal["none", "selected", "refresh_required", "unavailable"]
    selection_id: Id | None = None
    selection_digest: Digest | None = None
    confirmed_at: AwareDatetime | None = None
    label: str | None = None
    metric_family: Literal["actions"] | None = None
    api_version: Literal["v26.0"] | None = None
    spending_authorized: Literal[False] = False


class MetaCaptureView(CaptureView):
    profile: Literal["meta.website-purchase-count.campaign-day.v1"] = (
        "meta.website-purchase-count.campaign-day.v1"
    )
    present_count_rows: int = Field(ge=0, le=50000)
    explicit_zero_rows: int = Field(ge=0, le=50000)
    missing_count_rows: int = Field(ge=0, le=50000)
    monetary_value: Literal["unsupported"] = "unsupported"
    effective_attribution: Literal["unknown"] = "unknown"
    omitted_days: Literal["not_zero"] = "not_zero"


@dataclass(frozen=True)
class MetaCustomerRuntime:
    configuration: Settings
    transport: Callable[[], httpx.BaseTransport]
    clock: Callable[[], datetime]


def unavailable() -> HTTPException:
    return HTTPException(409, "meta_reporting_basis_changed")


class MetaCustomerService:
    def __init__(
        self,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        wid: int,
        sessions: Callable[[], Session],
        runtime: MetaCustomerRuntime | None,
    ) -> None:
        self.contexts = PlanningReadContexts(sessions, principal, provider, wid, principal.user.id)
        self.wid, self.actor, self.runtime, self.sessions = (
            wid,
            principal.user.id,
            runtime,
            sessions,
        )

    def now(self) -> datetime:
        value = self.runtime.clock() if self.runtime else datetime.now(UTC)
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
            raise unavailable()
        return value.astimezone(UTC)

    def guard(self, db: Session, aid: int, *, read: bool = False) -> None:
        self.contexts.authorize(db, self.wid, self.actor)
        original = self.contexts.principal.session
        current = db.get(CustomerSession, original.digest, populate_existing=True)
        if current is None or (current.authenticated_at, current.expires_at) != (
            original.authenticated_at,
            original.expires_at,
        ):
            raise HTTPException(401, "original customer session required")
        if lock_scope(db, self.wid, aid).platform.value != "meta_ads":
            raise unavailable()
        if read:
            if self.runtime is None:
                raise HTTPException(503, "meta_reporting_runtime_unavailable")
            paid_work(db, self.wid, self.now())
            controls = AutomationControlService(db)
            if (
                not self.runtime.configuration.meta_enabled
                or not controls.master_enabled(AutomationControlKey.ALL_DATA_SYNCS)
                or not controls.effective_enabled(self.wid, AutomationControlKey.META_ADS_SYNC)
            ):
                raise unavailable()

    def basis(
        self, db: Session, aid: int, starts: date, ends: date
    ) -> tuple[AggregateDependencyV1, str, str]:
        self.guard(db, aid, read=True)
        account = lock_scope(db, self.wid, aid)
        source = db.scalar(
            select(MetaConnection)
            .where(MetaConnection.workspace_id == self.wid, MetaConnection.account_id == aid)
            .execution_options(populate_existing=True)
        )
        pointer = db.get(CurrentPerformance, aid, populate_existing=True)
        completion = (
            db.get(PerformanceCompletion, pointer.completion_id, populate_existing=True)
            if pointer
            else None
        )
        if source is None or completion is None:
            raise unavailable()
        scope = ReportingScopeV1(
            workspace_id=self.wid,
            account_id=aid,
            connection_id=account.connection_id,
            platform="meta_ads",
            source_connection_ref=str(source.id),
            generation=source.generation,
            privacy_revision=completion.privacy_revision,
            native_account_id=source.external_account_id,
            currency=account.currency_code,
            time_zone=account.time_zone,
        )
        current_scope(db, scope)
        dependency = AggregateDependencyV1(
            completion_id=completion.id,
            manifest_digest=completion.manifest_digest,
            scope=scope,
            starts_on=completion.starts_on,
            ends_on=completion.ends_on,
        )
        _aggregate(db, dependency)
        if not (
            dependency.starts_on <= starts <= ends <= dependency.ends_on
            and ends < self.now().astimezone(ZoneInfo(scope.time_zone)).date()
        ):
            raise unavailable()
        grant = hashlib.sha256(source.encrypted_credentials.encode()).hexdigest()
        digest = hashlib.sha256(
            b"inlet.meta-customer-basis.v1\0"
            + _canonical(dependency)
            + query_profile_digest().encode()
            + grant.encode()
            + starts.isoformat().encode()
            + ends.isoformat().encode()
        ).hexdigest()
        return dependency, digest, grant

    def check_basis(
        self, db: Session, intent: BasisIntent | MetaSelectionIntent | MetaCapturePrepareIntent
    ) -> tuple[AggregateDependencyV1, str]:
        value, digest, grant = self.basis(db, intent.account_id, intent.starts_on, intent.ends_on)
        if digest != intent.basis_digest:
            raise unavailable()
        return value, grant

    def cas(self, db: Session, intent: SelectionIntent | InvalidationIntent) -> None:
        head = db.get(CurrentEventSelectionRow, intent.account_id, populate_existing=True)
        if ((head.selection_id, head.selection_digest) if head else (None, None)) != (
            intent.expected_selection_id,
            intent.expected_selection_digest,
        ):
            raise unavailable()

    @staticmethod
    def receipt(choice: CustomerEventSelectionV1) -> MetaSelectionView:
        if (
            choice.native_event_id,
            choice.api_version,
            choice.metric_family,
            choice.query_profile_digest,
        ) != (EVENT, "v26.0", "actions", query_profile_digest()):
            raise unavailable()
        return MetaSelectionView(
            account_id=choice.scope.account_id,
            state="selected",
            selection_id=choice.selection_id,
            selection_digest=selection_digest(choice),
            confirmed_at=choice.confirmed_at,
            label=LABEL,
            metric_family="actions",
            api_version="v26.0",
        )

    def state(self, aid: int) -> MetaSelectionView:
        with self.contexts.open() as db:
            self.guard(db, aid)
            head = db.get(CurrentEventSelectionRow, aid, populate_existing=True)
            if head is None:
                return MetaSelectionView(account_id=aid, state="none")
            if not head.invalidated:
                try:
                    return self.receipt(read_selection(db, self.wid, aid))
                except (ValueError, HTTPException):
                    pass
            return MetaSelectionView(
                account_id=aid,
                state="refresh_required" if head.invalidated else "unavailable",
                selection_id=head.selection_id,
                selection_digest=head.selection_digest,
            )

    def available_range(self, intent: AvailableRangeIntent) -> AvailableRangeView:
        with self.contexts.open() as db:
            dependency, digest, _ = self.basis(
                db, intent.account_id, intent.requested_starts_on, intent.requested_ends_on
            )
            if not (
                dependency.starts_on
                <= intent.requested_starts_on
                <= intent.requested_ends_on
                <= dependency.ends_on
                and intent.requested_ends_on
                < self.now().astimezone(ZoneInfo(dependency.scope.time_zone)).date()
            ):
                raise unavailable()
            return AvailableRangeView(
                **intent.model_dump(),
                basis_digest=digest,
                completion_id=dependency.completion_id,
                imported_starts_on=dependency.starts_on,
                imported_ends_on=dependency.ends_on,
                time_zone=dependency.scope.time_zone,
            )

    def options(self, intent: BasisIntent) -> MetaOptionsView:
        with self.contexts.open() as db:
            self.check_basis(db, intent)
            return MetaOptionsView(
                account_id=intent.account_id,
                basis_digest=intent.basis_digest,
                options=(MetaOptionView(option_id=intent.basis_digest),),
            )

    def confirm(self, intent: MetaSelectionIntent) -> MetaSelectionView:
        with self.contexts.write(lambda: None) as db:
            dependency, grant = self.check_basis(db, intent)
            self.cas(db, intent)
            if intent.option_id != intent.basis_digest:
                raise unavailable()
            head = db.get(CurrentEventSelectionRow, intent.account_id, populate_existing=True)
            if head and not head.invalidated:
                choice = read_selection(db, self.wid, intent.account_id)
                if choice.confirmed_by_customer_id != self.actor:
                    raise unavailable()
                result = self.receipt(choice)
            else:
                choice = CustomerEventSelectionV1(
                    selection_id=uuid4().hex,
                    scope=dependency.scope,
                    confirmed_by_customer_id=self.actor,
                    confirmed_at=self.now(),
                    event_namespace="meta_action_type",
                    native_event_owner_id=dependency.scope.native_account_id,
                    native_event_id=EVENT,
                    metric_family="actions",
                    api_version="v26.0",
                    query_profile_digest=query_profile_digest(),
                )
                store_selection(
                    db, choice, intent.expected_selection_id, intent.expected_selection_digest
                )
                result = self.receipt(choice)
            self.check_basis(db, intent)
            return result

    def invalidate(self, intent: InvalidationIntent) -> MetaSelectionView:
        with self.contexts.write(lambda: None) as db:
            self.guard(db, intent.account_id)
            self.cas(db, intent)
            invalidate_selected_account(db, self.wid, intent.account_id)
            self.guard(db, intent.account_id)
            return MetaSelectionView(
                account_id=intent.account_id,
                state="refresh_required",
                selection_id=intent.expected_selection_id,
                selection_digest=intent.expected_selection_digest,
            )

    @staticmethod
    def capture_receipt(value: SelectedCaptureV1) -> MetaCaptureView:
        req = value.request
        return MetaCaptureView(
            capture_id=req.capture_id,
            account_id=req.aggregate.scope.account_id,
            selection_id=req.selection.selection_id,
            selection_digest=req.selection_digest,
            starts_on=req.requested_starts_on,
            ends_on=req.requested_ends_on,
            completed_at=value.completed_at,
            returned_rows=len(value.facts),
            present_count_rows=sum(
                f.selected_conversions.presence == "present" for f in value.facts
            ),
            explicit_zero_rows=sum(
                f.selected_conversions.presence == "present" and f.selected_conversions.value == 0
                for f in value.facts
            ),
            missing_count_rows=sum(
                f.selected_conversions.presence == "missing" for f in value.facts
            ),
        )

    def capture_identifier(self, intent: MetaCapturePrepareIntent) -> str:
        assert self.runtime is not None
        fields = MetaCapturePrepareIntent.model_validate(intent.model_dump(exclude={"request_id"}))
        message = json.dumps(
            {
                "workspace_id": self.wid,
                "session_digest": self.contexts.principal.session.digest,
                "intent": fields.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return Vault(self.runtime.configuration).digest("meta-customer-capture.v1", message)[:32]

    def prepare_capture(self, intent: MetaCapturePrepareIntent) -> MetaCaptureIntent:
        with self.contexts.open() as db:
            self.check_basis(db, intent)
            self.cas(db, intent)
            self.receipt(read_selection(db, self.wid, intent.account_id))
            return MetaCaptureIntent(
                **intent.model_dump(), request_id=self.capture_identifier(intent)
            )

    def capture(self, intent: MetaCaptureIntent) -> MetaCaptureView:
        with self.contexts.open() as db:
            dependency, grant = self.check_basis(db, intent)
            if not hmac.compare_digest(intent.request_id, self.capture_identifier(intent)):
                raise unavailable()
            self.cas(db, intent)
            choice = read_selection(db, self.wid, intent.account_id)
            self.receipt(choice)
            previous = db.get(SelectedCaptureRow, intent.request_id, populate_existing=True)
            if previous:
                if (previous.workspace_id, previous.account_id) != (self.wid, intent.account_id):
                    raise unavailable()
                value = read_selected_capture(db, self.wid, intent.account_id, intent.request_id)
                r = value.request
                if (
                    r.selection_digest,
                    r.requested_starts_on,
                    r.requested_ends_on,
                    r.aggregate,
                ) != (
                    intent.expected_selection_digest,
                    intent.starts_on,
                    intent.ends_on,
                    dependency,
                ):
                    raise unavailable()
                return self.capture_receipt(value)
            settings = count_settings()
            request = SelectedCaptureRequestV1(
                schema_version="inlet.selected-capture-request.v2",
                settings=settings,
                capture_id=intent.request_id,
                aggregate=dependency,
                selection=choice,
                selection_digest=selection_digest(choice),
                requested_starts_on=intent.starts_on,
                requested_ends_on=intent.ends_on,
                started_at=self.now(),
                producer_contract=PRODUCER,
                query_profile_digest=query_profile_digest(),
                attribution=settings.effective,
            )
        assert self.runtime is not None
        with self.runtime.transport() as transport:
            value = acquire_selected(
                request,
                sessions=self.sessions,
                principal=self.contexts.principal,
                provider=self.contexts.provider,
                configuration=self.runtime.configuration,
                transport=transport,
                clock=self.runtime.clock,
                expected_grant_digest=grant,
            )
        return self.capture_receipt(value)
