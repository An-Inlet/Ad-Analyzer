"""Internal owned Meta count acquisition; no public route or default network factory."""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import Campaign
from app.automation.catalog import AutomationControlKey
from app.automation.service import AutomationControlService
from app.billing.entitlements import paid_work
from app.campaign_performance.selected_contracts import (
    SelectedCaptureRequestV1,
    SelectedCaptureV1,
    capture_request_digest,
)
from app.campaign_performance.selected_models import SelectedCaptureRow
from app.campaign_performance.selected_storage import (
    _aggregate,
    current_scope,
    read_selected_capture,
    read_selection,
    store_selected_capture,
)
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.meta.models import MetaConnection
from app.meta.security import MetaError, Vault
from app.meta.selected_collection import collect_meta_selected_capture
from app.meta.selected_http import MetaSelectedHTTPRead, SelectedMetaContext
from app.meta.selected_presence import validate_inputs
from app.planning_documents.read_context import PlanningReadContexts
from app.settings import Settings


class MetaSelectedAcquisitionUnavailable(ValueError):
    """No partial receipt, provider body or foreign scope is exposed."""


def acquire_selected(
    request: SelectedCaptureRequestV1,
    *,
    sessions: Callable[[], Session],
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    configuration: Settings,
    transport: httpx.BaseTransport,
    clock: Callable[[], datetime],
) -> SelectedCaptureV1:
    try:
        req = SelectedCaptureRequestV1.model_validate(request)
        scope = req.aggregate.scope
        wid, aid, actor = scope.workspace_id, scope.account_id, principal.user.id
        contexts = PlanningReadContexts(sessions, principal, provider, wid, actor)
        expected = capture_request_digest(req)

        def now() -> datetime:
            value = clock()
            if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("aware clock required")
            return value.astimezone(UTC)

        def guard(db: Session) -> MetaConnection:
            contexts.authorize(db, wid, actor)
            paid_work(db, wid, now())
            controls = AutomationControlService(db)
            if (
                not configuration.meta_enabled
                or not controls.master_enabled(AutomationControlKey.ALL_DATA_SYNCS)
                or not controls.effective_enabled(wid, AutomationControlKey.META_ADS_SYNC)
            ):
                raise ValueError("reporting disabled")
            current_scope(db, scope)
            _aggregate(db, req.aggregate)
            if read_selection(db, wid, aid) != req.selection:
                raise ValueError("selection changed")
            source = db.get(
                MetaConnection, int(scope.source_connection_ref), populate_existing=True
            )
            if source is None:
                raise ValueError("source unavailable")
            return source

        def mapping(db: Session) -> dict[str, int]:
            rows = list(
                db.scalars(
                    select(Campaign)
                    .where(Campaign.account_id == aid, Campaign.platform == "meta_ads")
                    .order_by(Campaign.id)
                    .limit(50_001)
                    .execution_options(populate_existing=True)
                )
            )
            result = {row.external_campaign_id: row.id for row in rows}
            if len(result) != len(rows):
                raise ValueError("ambiguous mapping")
            validate_inputs(req, result)
            return result

        def existing(db: Session) -> SelectedCaptureV1 | None:
            row = db.get(SelectedCaptureRow, req.capture_id, populate_existing=True)
            if row is None:
                return None
            if (row.workspace_id, row.account_id) != (wid, aid):
                raise ValueError("capture unavailable")
            found = read_selected_capture(db, wid, aid, req.capture_id)
            if found.request_digest != expected:
                raise ValueError("capture replay changed")
            return found

        with contexts.open() as db:
            source = guard(db)
            owned_mapping = mapping(db)
            previous = existing(db)
            if previous is not None:
                return previous
            grant = hashlib.sha256(source.encrypted_credentials.encode()).digest()
            bundle = Vault(configuration).open(
                wid, scope.native_account_id, source.encrypted_credentials
            )
            token, expiry = bundle["access_token"], bundle["expires_at"]
            if type(token) is not str or not 1 <= len(token) <= 16384 or type(expiry) is not str:
                raise ValueError("grant unavailable")
            secret = configuration.meta_client_secret
            if secret is None:
                raise ValueError("configuration unavailable")
            context = SelectedMetaContext(
                request_digest=expected,
                expires_at=datetime.fromisoformat(expiry),
                access_token=SecretStr(token),
                app_secret=secret,
            )
            contexts.authorize(db, wid, actor)

        def revalidate(supplied: SelectedCaptureRequestV1) -> None:
            if capture_request_digest(supplied) != expected:
                raise ValueError("request changed")
            with contexts.open() as db:
                source = guard(db)
                if (
                    hashlib.sha256(source.encrypted_credentials.encode()).digest() != grant
                    or mapping(db) != owned_mapping
                ):
                    raise ValueError("source changed")
                if not req.started_at <= now() < req.started_at + timedelta(seconds=60):
                    raise ValueError("request expired")

        def context_reader(supplied: SelectedCaptureRequestV1) -> SelectedMetaContext:
            revalidate(supplied)
            return context

        reader = MetaSelectedHTTPRead(context_reader, revalidate, transport=transport, clock=clock)
        capture = collect_meta_selected_capture(req, owned_mapping, reader, revalidate, clock)

        def final_deadline() -> None:
            if not req.started_at <= now() < req.started_at + timedelta(seconds=60):
                raise ValueError("request expired")

        with contexts.write(final_deadline) as db:
            source = guard(db)
            if (
                hashlib.sha256(source.encrypted_credentials.encode()).digest() != grant
                or mapping(db) != owned_mapping
            ):
                raise ValueError("source changed")
            winner = existing(db)
            if winner is None:
                store_selected_capture(db, capture)
                winner = read_selected_capture(db, wid, aid, req.capture_id)
            db.flush()
            guard(db)
            if not req.started_at <= now() < req.started_at + timedelta(seconds=60):
                raise ValueError("request expired")
            contexts.authorize(db, wid, actor)
            return winner
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        ArithmeticError,
        MetaError,
        HTTPException,
    ):
        raise MetaSelectedAcquisitionUnavailable("meta_selected_acquisition_unavailable") from None
