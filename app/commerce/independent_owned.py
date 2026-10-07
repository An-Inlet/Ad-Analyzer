"""Original-session-owned acquisition -> atomic v2 publication, no default wiring."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commerce.evidence import digest, lock_workspace
from app.commerce.independent import IndependentAcquirer
from app.commerce.independent_contracts import (
    ScanCompletion,
    ScanLimits,
    ScanPermit,
    ScanRequest,
    ScanUnavailable,
)
from app.commerce.ledger import DEFINITION, lock_store, retention_floor
from app.commerce.models import (
    CommerceEvidenceState,
    CommerceMeasurementPublication,
    CommerceStore,
    CommerceSuppression,
)
from app.commerce.publication_contracts import IndependentManifest, parse_publication
from app.customers.access import CustomerPrincipal, lock_customer_mutation
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.goals.models import Goal, GoalRevision
from app.goals.schemas import GoalDefinition
from app.outcomes.contracts import Window
from app.outcomes.maturity import MaturityScope
from app.settings import Settings
from app.shopify.models import ShopifyConnection
from app.shopify.privacy_identity import markers
from app.shopify.security import ShopifyError, Vault, utc
from app.workspaces.models import Workspace, WorkspaceIntegration

Sessions = Callable[[], Session]
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class _OriginalIdentity:
    user_id: str
    session_digest: str
    issuer: str
    subject: str
    authenticated_at: int


class OwnedAcquisition:
    """Server-injected identity provider/settings; no browser-supplied proof.

    CSRF/origin verification remains the responsibility of a future HTTP caller.
    This service has no route or default factory, and never refreshes credentials.
    """

    def __init__(
        self,
        sessions: Sessions,
        principal: CustomerPrincipal,
        identity: IdentityProvider,
        settings: Settings,
        *,
        environment: Literal["contract_test", "live"],
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self.sessions, self.identity, self.settings = sessions, identity, settings
        self.environment, self.clock = environment, clock
        self.original = _OriginalIdentity(
            principal.user.id,
            principal.session.digest,
            principal.user.issuer,
            principal.user.subject,
            principal.session.authenticated_at,
        )

    def _authorize(self, db: Session, wid: int) -> None:
        lock_workspace(db, wid, active=True)
        user = db.get(CustomerUser, self.original.user_id)
        session = db.get(CustomerSession, self.original.session_digest)
        if (
            user is None
            or session is None
            or (user.issuer, user.subject, session.user_id, session.authenticated_at)
            != (
                self.original.issuer,
                self.original.subject,
                self.original.user_id,
                self.original.authenticated_at,
            )
        ):
            raise ScanUnavailable("acquisition_authority_changed")
        lock_customer_mutation(db, CustomerPrincipal(user, session), wid, self.identity)
        membership = db.get(CustomerMembership, (user.id, wid), populate_existing=True)
        if (
            (user.id, session.digest, user.issuer, user.subject, session.authenticated_at)
            != (
                self.original.user_id,
                self.original.session_digest,
                self.original.issuer,
                self.original.subject,
                self.original.authenticated_at,
            )
            or membership is None
            or membership.role != "owner"
            or membership.status != "active"
        ):
            raise ScanUnavailable("acquisition_authority_changed")

    def _resolve(
        self,
        db: Session,
        wid: int,
        sid: str,
        gid: str,
        revision: int,
        start: date,
        end: date,
        acquisition_id: str,
    ) -> tuple[ScanRequest, ScanPermit, CommerceStore, CommerceEvidenceState]:
        self._authorize(db, wid)
        native = db.scalar(
            select(ShopifyConnection)
            .where(
                ShopifyConnection.workspace_id == wid,
                ShopifyConnection.commerce_store_id == sid,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        store = db.scalar(
            select(CommerceStore)
            .where(
                CommerceStore.id == sid,
                CommerceStore.workspace_id == wid,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            native is None
            or store is None
            or native.status != "connected"
            or store.status != "active"
        ):
            raise ScanUnavailable("acquisition_source_unavailable")
        integration = db.scalar(
            select(WorkspaceIntegration)
            .where(
                WorkspaceIntegration.id == store.connection_id,
                WorkspaceIntegration.workspace_id == wid,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        fence = db.scalar(
            select(CommerceEvidenceState)
            .where(
                CommerceEvidenceState.store_id == sid,
                CommerceEvidenceState.workspace_id == wid,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            integration is None
            or integration.provider != "shopify"
            or integration.status != "active"
            or native.workspace_integration_id != integration.id
            or fence is None
            or (native.shop_domain, native.currency_code, native.time_zone)
            != (store.shop_domain, store.currency, store.time_zone)
        ):
            raise ScanUnavailable("acquisition_source_unavailable")
        goal = db.scalar(
            select(Goal)
            .where(Goal.id == gid, Goal.workspace_id == wid)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        version = db.get(GoalRevision, (gid, revision), populate_existing=True)
        if (
            goal is None
            or goal.revision != revision
            or version is None
            or (version.workspace_id != wid or version.confirmed_at is None)
        ):
            raise ScanUnavailable("acquisition_goal_changed")
        definition = GoalDefinition.model_validate(version.definition)
        if (
            definition.store_id,
            definition.target_window.currency,
            definition.target_window.time_zone,
        ) != (sid, store.currency, store.time_zone):
            raise ScanUnavailable("acquisition_goal_changed")
        window = Window.local(start, end, store.time_zone)
        # Fresh clock after every blocking authority/source lock, not entry time.
        now = utc(self.clock())
        if window.start_utc < retention_floor(now, store.time_zone) or window.end_utc > now:
            raise ScanUnavailable("acquisition_window_unavailable")
        if (
            markers(db, store)
            or db.scalar(
                select(CommerceSuppression.object_key)
                .where(
                    CommerceSuppression.workspace_id == wid,
                    CommerceSuppression.shop_key == store.shop_key,
                )
                .limit(1)
            )
            is not None
        ):
            raise ScanUnavailable("acquisition_privacy_unresolved")
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        vault = Vault(self.settings)
        bundle = vault.open(wid, native.shop_domain, native.encrypted_credentials)
        token = bundle.get("access_token")
        expires = bundle.get("expires_at")
        expiry = utc(datetime.fromisoformat(expires)) if expires else now + timedelta(minutes=30)
        if not isinstance(token, str) or not 8 <= len(token) <= 4096 or expiry <= now:
            raise ScanUnavailable("acquisition_credentials_expired")
        key = self.settings.shopify_identifier_hash_key
        if key is None:
            raise ScanUnavailable("acquisition_credentials_unavailable")
        connection_version = digest(
            [
                "inlet.independent-source-binding.v1",
                native.id,
                native.workspace_integration_id,
                utc(native.connected_at).isoformat(),
                integration.integration_key,
                store.revision,
                vault.digest("independent_grant", native.encrypted_credentials),
            ]
        )
        request = ScanRequest(
            acquisition_id=acquisition_id,
            scope=MaturityScope(
                workspace_id=wid,
                store_id=sid,
                generation=fence.generation,
                privacy_epoch=fence.privacy_epoch,
                goal_id=gid,
                goal_revision=revision,
                goal_digest=digest(definition.model_dump(mode="json")),
                metric_definition_digest=digest(DEFINITION),
                currency=store.currency,
                time_zone=store.time_zone,
            ),
            connection_id=integration.id,
            connection_version=connection_version,
            export_privacy_revision=workspace.export_privacy_revision,
            start=start,
            end=end,
        )
        return (
            request,
            ScanPermit(
                request_digest=request.request_digest,
                expires_at=expiry,
                shop_domain=native.shop_domain,
                shop_key=store.shop_key,
                token=SecretStr(token),
                identifier_key=key,
                active=True,
                privacy_resolved=True,
            ),
            store,
            fence,
        )

    def capture(
        self,
        wid: int,
        sid: str,
        gid: str,
        revision: int,
        start: date,
        end: date,
    ) -> ScanRequest:
        try:
            with self.sessions() as db:
                request, _, _, _ = self._resolve(
                    db, wid, sid, gid, revision, start, end, uuid4().hex
                )
                return request
        except (HTTPException, ShopifyError, ValueError, TypeError, KeyError):
            raise ScanUnavailable("acquisition_authority_unavailable") from None

    def _check(
        self,
        db: Session,
        request: ScanRequest,
    ) -> tuple[ScanPermit, CommerceStore, CommerceEvidenceState]:
        scope = request.scope
        current, permit, store, fence = self._resolve(
            db,
            scope.workspace_id,
            scope.store_id,
            scope.goal_id,
            scope.goal_revision,
            request.start,
            request.end,
            request.acquisition_id,
        )
        if current != request:
            raise ScanUnavailable("acquisition_authority_changed")
        return permit, store, fence

    def authority(self, request: ScanRequest, _observed: datetime) -> ScanPermit:
        try:
            with self.sessions() as db:
                permit, _, _ = self._check(db, request)
                return permit  # Context closes transaction before Shopify HTTP.
        except (HTTPException, ShopifyError, ValueError, TypeError, KeyError):
            raise ScanUnavailable("acquisition_authority_unavailable") from None

    def acquire_and_publish(
        self,
        request: ScanRequest,
        *,
        transport: httpx.BaseTransport | None = None,
        limits: ScanLimits | None = None,
    ) -> str:
        completion = IndependentAcquirer(
            self.authority,
            transport=transport,
            clock=self.clock,
            limits=limits,
        ).acquire(request)
        return self._publish(completion)

    def _publish(self, completion: ScanCompletion) -> str:
        with self.sessions() as db:
            identifier = self.publish_in_transaction(db, completion)
            db.commit()
            return identifier

    def publish_in_transaction(self, db: Session, completion: ScanCompletion) -> str:
        """Internal owned write; caller commits this with its leased completion receipt."""
        completion = ScanCompletion.model_validate(completion.model_dump())
        _, store, fence = self._check(db, completion.request)
        now = utc(self.clock())
        if not completion.started_at <= completion.completed_at <= now:
            raise ScanUnavailable("acquisition_time_invalid")
        key = digest(
            ["inlet.commerce-independent-completion.v2", completion.model_dump(mode="json")]
        )
        previous = db.scalar(
            select(CommerceMeasurementPublication).where(
                CommerceMeasurementPublication.workspace_id == store.workspace_id,
                CommerceMeasurementPublication.store_id == store.id,
                CommerceMeasurementPublication.completion_digest == key,
            )
        )
        if previous is not None:
            existing = parse_publication(previous)
            if (
                not isinstance(existing, IndependentManifest)
                or existing.environment != self.environment
            ):
                raise ScanUnavailable("acquisition_environment_mismatch")
            return previous.id
        fence.publication_revision += 1
        fence.updated_at = now
        manifest = IndependentManifest(
            workspace_id=store.workspace_id,
            store_id=store.id,
            generation=fence.generation,
            privacy_epoch=fence.privacy_epoch,
            publication_revision=fence.publication_revision,
            source_revision=store.revision,
            source="shopify",
            source_api_version=completion.source_api_version,
            source_window_start=completion.started_at,
            source_window_end=completion.completed_at,
            as_of=now,
            definition=DEFINITION,
            definition_digest=digest(DEFINITION),
            currency=store.currency,
            time_zone=store.time_zone,
            unit="monetary_micros",
            grain="store_local_day",
            attribution="not_applicable_store_total",
            environment=self.environment,
            acquisition=completion,
        )
        raw = manifest.model_dump(mode="json")
        row = CommerceMeasurementPublication(
            id=uuid4().hex,
            workspace_id=store.workspace_id,
            store_id=store.id,
            generation=fence.generation,
            privacy_epoch=fence.privacy_epoch,
            publication_revision=fence.publication_revision,
            source_revision=store.revision,
            source_window_start=completion.started_at,
            source_window_end=completion.completed_at,
            published_at=now,
            earliest_source_day=completion.request.start,
            completion_digest=key,
            manifest_digest=digest(raw),
            manifest=raw,
        )
        db.add(row)
        db.flush()
        # Repeat original authority and fresh retention under held source/session locks.
        self._check(db, completion.request)
        parse_publication(row)
        return row.id


    def load(self, wid: int, identifier: str) -> IndependentManifest:
        with self.sessions() as db:
            self._authorize(db, wid)
            row = db.scalar(
                select(CommerceMeasurementPublication).where(
                    CommerceMeasurementPublication.workspace_id == wid,
                    CommerceMeasurementPublication.id == identifier,
                )
            )
            if row is None:
                raise HTTPException(404, "measurement publication unavailable")
            document = parse_publication(row)
            if (
                not isinstance(document, IndependentManifest)
                or document.environment != self.environment
            ):
                raise HTTPException(404, "independent publication unavailable")
            # Historical provenance does not require retaining a live token or
            # an unchanged incremental revision. It does require current privacy,
            # ownership, active source and retention; it never grants eligibility.
            store = lock_store(db, row.store_id, wid)
            fence = db.get(CommerceEvidenceState, store.id, populate_existing=True)
            evaluated = utc(self.clock())
            window = Window.local(
                document.acquisition.request.start,
                document.acquisition.request.end,
                store.time_zone,
            )
            if (
                fence is None
                or (row.generation, row.privacy_epoch) != (fence.generation, fence.privacy_epoch)
                or (document.currency, document.time_zone) != (store.currency, store.time_zone)
                or window.start_utc < retention_floor(evaluated, store.time_zone)
                or document.as_of > evaluated
            ):
                raise HTTPException(404, "independent publication unavailable")
            self._authorize(db, wid)
            return document
