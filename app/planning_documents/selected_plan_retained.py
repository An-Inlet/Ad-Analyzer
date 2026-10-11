"""Current SQL-only v4 commitments; caller owns external identity freshness.

Call inside the caller's original authorized transaction, with authorization again
before accepting the result. This port grants no provider or mutation authority.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.campaign_performance.selected_models import CurrentEventSelectionRow
from app.customers.access import CustomerPrincipal
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.meta.models import MetaConnection
from app.planning_documents.context import AccountRef
from app.planning_documents.evidence_local import changed
from app.planning_documents.retained_sources import _guard, _reporting
from app.planning_documents.selected_inputs import SelectedCaptureSelectorV1
from app.planning_documents.selected_plan_proof import (
    SelectedHeadProofV1,
    SelectedRetainedAccountProofV1,
)
from app.planning_documents.selected_plan_reader import load_selected_plan_graph
from app.planning_documents.source_contracts import SourceFence
from app.shopify.security import utc
from app.sources.models import SourceConnection


def _head(db: Session, account: AccountRef) -> SelectedHeadProofV1 | None:
    row = (
        db.execute(
            select(CurrentEventSelectionRow.__table__).where(
                CurrentEventSelectionRow.account_id == account.account_id
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    if (row["workspace_id"], row["connection_id"]) != (account.workspace_id, account.connection_id):
        raise changed()
    return SelectedHeadProofV1(
        selection_id=row["selection_id"],
        selection_digest=row["selection_digest"],
        invalidated=row["invalidated"],
    )


def _private_source(db: Session, account: AccountRef) -> dict[str, Any]:
    # Private grant/login changes must not hide behind unchanged public generation.
    # This transient comparison is never returned, hashed, persisted or logged.
    model: Any = {
        "google_ads": GoogleCustomerConnection,
        "meta_ads": MetaConnection,
        "tiktok_ads": SourceConnection,
    }[account.platform]
    rows = (
        db.execute(
            select(model.__table__).where(
                model.workspace_id == account.workspace_id, model.account_id == account.account_id
            )
        )
        .mappings()
        .fetchmany(2)
    )
    if len(rows) != 1:
        raise changed()
    return dict(rows[0])


def capture_selected_reporting_pin(
    db: Session,
    principal: CustomerPrincipal,
    account: AccountRef,
    privacy: int,
    selector: SelectedCaptureSelectorV1 | None,
    now: datetime,
) -> SelectedRetainedAccountProofV1:
    """Capture exact current reporting and explicit selected input, never latest.

    READ_ROLES are intentional: currentness/history readers include viewers.
    External identity refresh and its final age check remain caller obligations;
    no identity provider is invoked under the SQL locks acquired here.
    """
    account = AccountRef.model_validate(account)
    if selector is not None:
        selector = SelectedCaptureSelectorV1.model_validate(selector)
        if selector.account_id != account.account_id:
            raise changed()
    if now.tzinfo is None or type(privacy) is not int or privacy < 0:
        raise changed()
    root = db.get_transaction()
    if root is None:
        raise changed()
    connection = db.connection()
    transaction = connection.get_transaction()
    actor = principal.user.id
    original_session = principal.session.digest

    def guard() -> None:
        if (
            db.get_transaction() is not root
            or not root.is_active
            or db.in_nested_transaction()
            or db.new
            or db.dirty
            or db.deleted
            or connection.get_transaction() is not transaction
            or (principal.user.id, principal.session.digest) != (actor, original_session)
        ):
            raise changed()
        _guard(db, principal, account.workspace_id, actor)
        if (
            workspace_export_revision(db, account.workspace_id) != privacy
            or principal.session.expires_at <= max(utc(now), database_utc_now(db)).timestamp()
        ):
            raise changed()

    def proof() -> SelectedRetainedAccountProofV1:
        binding, reporting = _reporting(db, principal, account, privacy, qualified=True)
        fence = SourceFence(
            account=account,
            source_binding_digest=binding,
            source_revision=account.connection_version,
            privacy_revision=privacy,
        )
        head = _head(db, account)
        pin = (
            None
            if selector is None
            else load_selected_plan_graph(
                db, account=account, expected_source=fence, capture_id=selector.capture_id
            ).pin()
        )
        return SelectedRetainedAccountProofV1(
            source_fence=fence,
            legacy_reporting_digest=reporting,
            selection_head=head,
            capture_pin=pin,
        )

    with db.no_autoflush:
        guard()
        private = _private_source(db, account)
        result = proof()
        guard()
        # Recompute after the complete read: raw SQL mutations and late pointer /
        # campaign changes cannot be accepted merely because ORM state was cached.
        if proof() != result or _private_source(db, account) != private:
            raise changed()
        guard()
        return result
