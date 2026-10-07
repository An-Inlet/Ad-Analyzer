"""Google-only ordinary customer composition with server-owned evidence sources."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.collectors.account_diagnostics import _BorrowedTransport
from app.collectors.google_catalog import GoogleCatalogHTTP
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.executors.google_activation import GoogleActivationHTTP
from app.executors.google_publication import GooglePublicationHTTP
from app.executors.meta_activation import MetaActivationHTTP
from app.executors.meta_publication import MetaPublicationTransport
from app.executors.tiktok_activation import TikTokActivationHTTP
from app.executors.tiktok_publication import TikTokPublicationTransport
from app.production_runtime.configuration import load_google_execution_manifest
from app.production_runtime.contracts import (
    GoogleExecutionManifestV1,
    RegisteredGoogleEvidenceSource,
    admit_source,
)
from app.production_runtime.owned_google_contexts import (
    google_execution_transport,
    owned_google_contexts,
)
from app.publication.activation import ActivationRuntime
from app.publication.activation_review import ActivationReviewRuntime
from app.publication.coordinator_contracts import (
    ConfigurationQualification,
    CreationPlan,
    CreationRuntime,
)
from app.publication.customer_authority import bind_authority
from app.publication.customer_runtime import CustomerExecutionRuntime
from app.publication.execution_contracts import (
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
)
from app.publication.google_qualification import qualify_google
from app.publication.provider_contracts import ProviderPublishPlan
from app.publication.social_contracts import (
    ProviderMediaBinding,
    SocialBoundRequest,
    SocialProviderContext,
)
from app.settings import Settings


def registered_google_evidence(source_id: str) -> RegisteredGoogleEvidenceSource | None:
    """Trusted deployment composition seam; no live or test source ships installed."""
    return None


@lru_cache(maxsize=4)
def pinned_manifest(path: str | None, digest: str | None) -> GoogleExecutionManifestV1 | None:
    return load_google_execution_manifest(path, digest)


def execution_clock() -> datetime:
    return datetime.now(UTC)


def google_plan(plan: CreationPlan) -> ProviderPublishPlan:
    if (
        not isinstance(plan, ProviderPublishPlan)
        or plan.review.scope.account.platform != "google_ads"
    ):
        raise HTTPException(409, "google_execution_provider_unsupported")
    return plan


class DisabledSocialMedia:
    def read_verified(self, workspace_id: int, binding: ProviderMediaBinding) -> bytes:
        raise HTTPException(409, "google_execution_provider_unsupported")


def reject_social(request: SocialBoundRequest) -> SocialProviderContext:
    raise HTTPException(409, "google_execution_provider_unsupported")


@contextmanager
def configured_google_execution(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    configuration: Settings,
    *,
    clock: Callable[[], datetime] | None = None,
) -> Iterator[CustomerExecutionRuntime | None]:
    clock = clock or execution_clock
    manifest = pinned_manifest(
        configuration.google_execution_manifest_path, configuration.google_execution_manifest_digest
    )
    if manifest is None:
        yield None
        return
    registered = admit_source(manifest, registered_google_evidence(manifest.evidence_source_id))
    if registered is None:
        yield None
        return
    actor = principal.user.id
    authorize = bind_authority(principal, provider)
    engine = db.get_bind()

    def sessions() -> Session:
        return Session(engine)

    evidence = registered.build(sessions, authorize, actor, clock)
    if evidence.descriptor != registered.descriptor:
        raise HTTPException(409, "google_execution_evidence_source_changed")
    # No principal is global. Source admission precedes credential/transport construction.
    transport = google_execution_transport(manifest)
    try:
        with owned_google_contexts(
            sessions, authorize, actor, manifest, configuration, clock, transport
        ) as contexts:
            borrowed = _BorrowedTransport(transport)
            google = GooglePublicationHTTP(transport=borrowed)

            def qualification(plan: CreationPlan, now: datetime) -> ConfigurationQualification:
                concrete = google_plan(plan)
                result = qualify_google(
                    concrete.review, contexts.publication(concrete.review.scope), google, now
                )
                return ConfigurationQualification(
                    environment=manifest.environment,
                    account=ExecutionAccount.from_publication(concrete.review.scope),
                    plan_digest=concrete.digest(),
                    api_version=manifest.api_version,
                    observed_at=result.observed_at,
                    expires_at=result.expires_at,
                    evidence_digest=result.evidence_digest,
                    checks_version="google.configuration.readback.v25",
                    unresolved=[],
                )

            def exposure(
                session: Session, binding: ProviderMandateBinding, plan: CreationPlan, now: datetime
            ) -> ExposureEvidence:
                google_plan(plan)
                return evidence.creation(session, binding, plan, now)

            def activation_exposure(
                session: Session,
                binding: ProviderMandateBinding,
                plan: CreationPlan,
                reservation_id: str,
                now: datetime,
            ) -> ExposureEvidence:
                google_plan(plan)
                return evidence.activation(session, binding, plan, reservation_id, now)

            creation = CreationRuntime(
                environment=manifest.environment,
                qualification_reader=qualification,
                exposure_reader=exposure,
                google=google,
                meta=MetaPublicationTransport(DisabledSocialMedia(), transport=borrowed),
                tiktok=TikTokPublicationTransport(DisabledSocialMedia(), transport=borrowed),
                google_context=lambda request: contexts.publication(request.scope),
                social_context=reject_social,
                live_enabled=manifest.live_execution_enabled,
                authorize=authorize,
            )
            activation = (
                ActivationRuntime(
                    review=ActivationReviewRuntime(creation, activation_exposure),
                    google=GoogleActivationHTTP(transport=borrowed),
                    meta=MetaActivationHTTP(DisabledSocialMedia(), transport=borrowed),
                    tiktok=TikTokActivationHTTP(DisabledSocialMedia(), transport=borrowed),
                    context=contexts.activation,
                )
                if manifest.activation_enabled
                else None
            )
            yield CustomerExecutionRuntime(
                creation=creation,
                activation=activation,
                google_qualification=google,
                google_context=contexts.publication,
                catalog=GoogleCatalogHTTP(contexts.catalog, transport=borrowed, clock=clock),
                clock=clock,
            )
    finally:
        transport.close()
