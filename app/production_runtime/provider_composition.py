"""Request-local lazy Google/Meta/TikTok composition, selected by typed owned operations."""

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.campaign_review.contracts import MediaStore
from app.collectors.account_diagnostics import _BorrowedTransport
from app.collectors.meta_catalog import MetaCatalogHTTP
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.executors.google_activation import GoogleActivationHTTP
from app.executors.google_publication import GooglePublicationHTTP
from app.executors.meta_activation import MetaActivationHTTP
from app.executors.meta_publication import MetaPublicationTransport
from app.executors.tiktok_activation import TikTokActivationHTTP
from app.executors.tiktok_publication import TikTokPublicationTransport
from app.production_runtime import assembly
from app.production_runtime.contracts import admit_source
from app.production_runtime.meta_configuration import (
    MetaConfigurationBundleV1,
    load_meta_execution_configuration,
)
from app.production_runtime.meta_contracts import (
    MetaExecutionEvidence,
    MetaExecutionManifestV1,
    RegisteredMetaEvidenceSource,
    admit_meta_source,
)
from app.production_runtime.meta_transport import meta_execution_transport
from app.production_runtime.owned_meta_contexts import OwnedMetaContexts, OwnedMetaMedia
from app.production_runtime.owned_tiktok_contexts import OwnedTikTokContexts, OwnedTikTokMedia
from app.production_runtime.tiktok_configuration import (
    TikTokConfigurationBundleV1,
    TikTokRuntimeConfigurationError,
    load_tiktok_execution_configuration,
)
from app.production_runtime.tiktok_contracts import (
    TikTokExecutionEvidence,
    TikTokExecutionManifestV1,
    admit_tiktok_source,
    registered_tiktok_evidence,
)
from app.production_runtime.tiktok_transport import tiktok_execution_transport
from app.publication.activation import ActivationRuntime
from app.publication.activation_contracts import ActivationContext, ActivationRequest
from app.publication.activation_review import ActivationReviewRuntime
from app.publication.contracts import PublicationScope
from app.publication.coordinator_contracts import (
    ConfigurationQualification,
    CreationPlan,
    CreationRuntime,
)
from app.publication.customer_authority import bind_authority
from app.publication.customer_catalog import GoogleCatalog, GoogleCatalogRequest
from app.publication.customer_runtime import CustomerExecutionRuntime
from app.publication.execution_contracts import ExposureEvidence, ProviderMandateBinding
from app.publication.provider_contracts import BoundProviderRequest, ProviderContext
from app.publication.social_catalog import SocialCatalog, SocialCatalogRequest
from app.publication.social_contracts import (
    ProviderMediaBinding,
    SocialBoundRequest,
    SocialProviderContext,
    SocialPublishPlan,
)
from app.publication.social_review_contracts import SocialConfigurationDocument
from app.publication.social_review_runtime import SocialReviewRuntime
from app.settings import Settings


def registered_meta_evidence(source_id: str) -> RegisteredMetaEvidenceSource | None:
    """Trusted Python deployment seam; no source implementation ships enabled."""
    return None


@lru_cache(maxsize=4)
def pinned_meta(
    path: str | None, digest: str | None, bundle_path: str | None
) -> tuple[MetaExecutionManifestV1, MetaConfigurationBundleV1] | None:
    return load_meta_execution_configuration(path, digest, bundle_path)


@dataclass(frozen=True)
class MetaResources:
    contexts: OwnedMetaContexts
    media: OwnedMetaMedia
    transport: httpx.BaseTransport
    evidence: MetaExecutionEvidence


@lru_cache(maxsize=4)
def pinned_tiktok(
    path: str | None, digest: str | None, bundle_path: str | None
) -> tuple[TikTokExecutionManifestV1, TikTokConfigurationBundleV1] | None:
    return load_tiktok_execution_configuration(path, digest, bundle_path)


@dataclass(frozen=True)
class TikTokResources:
    contexts: OwnedTikTokContexts
    media: OwnedTikTokMedia
    transport: httpx.BaseTransport
    evidence: TikTokExecutionEvidence


class DisabledTransport(httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise HTTPException(409, "provider_execution_not_configured")


class LazyMetaTransport(httpx.BaseTransport):
    def __init__(self, resolve: Callable[[], MetaResources | TikTokResources]) -> None:
        self.resolve = resolve

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self.resolve().transport.handle_request(request)

    def close(self) -> None:
        pass  # Request ExitStack owns the underlying resource, not borrowed clients.


class LazyMetaMedia:
    def __init__(self, resolve: Callable[[], MetaResources | TikTokResources]) -> None:
        self.resolve = resolve

    def read_verified(self, workspace_id: int, binding: ProviderMediaBinding) -> bytes:
        return self.resolve().media.read_verified(workspace_id, binding)


class LazyGoogleHTTP(GooglePublicationHTTP):
    def __init__(self, resolve: Callable[[], CustomerExecutionRuntime]) -> None:
        super().__init__()
        self.resolve = resolve

    def _post(
        self,
        request: BoundProviderRequest,
        context: ProviderContext,
        suffix: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        if request.scope.account.platform != "google_ads":
            raise HTTPException(409, "provider_execution_not_configured")
        return self.resolve().google_qualification._post(request, context, suffix, body)


@contextmanager
def configured_execution(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    configuration: Settings,
    media_store: Callable[[], MediaStore],
    *,
    social_only: bool = False,
) -> Iterator[CustomerExecutionRuntime | None]:
    """No source build/credentials/HTTP until an admitted typed provider is used."""
    clock = assembly.execution_clock
    meta_config = pinned_meta(
        configuration.meta_execution_manifest_path,
        configuration.meta_execution_manifest_digest,
        configuration.meta_execution_bundle_path,
    )
    try:
        tiktok_config = pinned_tiktok(
            configuration.tiktok_execution_manifest_path,
            configuration.tiktok_execution_manifest_digest,
            configuration.tiktok_execution_bundle_path,
        )
    except TikTokRuntimeConfigurationError:
        raise HTTPException(503, "tiktok_execution_configuration_unavailable") from None
    if social_only and meta_config is None and tiktok_config is None:
        yield None
        return
    google_manifest = assembly.pinned_manifest(
        configuration.google_execution_manifest_path,
        configuration.google_execution_manifest_digest,
    )
    environments = {
        value.environment
        for value in (
            google_manifest,
            meta_config[0] if meta_config else None,
            tiktok_config[0] if tiktok_config else None,
        )
        if value is not None
    }
    if len(environments) > 1:
        raise HTTPException(409, "provider_execution_environment_mismatch")
    google_source = (
        admit_source(
            google_manifest, assembly.registered_google_evidence(google_manifest.evidence_source_id)
        )
        if google_manifest is not None
        else None
    )
    meta_source = (
        admit_meta_source(
            meta_config[0], registered_meta_evidence(meta_config[0].evidence_source_id)
        )
        if meta_config is not None
        else None
    )
    tiktok_source = (
        admit_tiktok_source(
            tiktok_config[0], registered_tiktok_evidence(tiktok_config[0].evidence_source_id)
        )
        if tiktok_config is not None
        else None
    )
    if google_source is None and meta_source is None and tiktok_source is None:
        yield None
        return
    manifest = (
        google_manifest
        if google_source is not None
        else meta_config[0]
        if meta_source is not None and meta_config
        else tiktok_config[0]
        if tiktok_config
        else None
    )
    assert manifest is not None
    actor, authorize, engine = principal.user.id, bind_authority(principal, provider), db.get_bind()

    def sessions() -> Session:
        return Session(engine)

    with ExitStack() as stack:
        google_runtime: CustomerExecutionRuntime | None = None
        meta_resource: MetaResources | None = None
        tiktok_resource: TikTokResources | None = None

        def google() -> CustomerExecutionRuntime:
            nonlocal google_runtime
            if google_source is None:
                raise HTTPException(409, "provider_execution_not_configured")
            if google_runtime is None:
                google_runtime = stack.enter_context(
                    assembly.configured_google_execution(
                        db,
                        principal,
                        provider,
                        configuration,
                        clock=clock,
                    )
                )
            if google_runtime is None:
                raise HTTPException(409, "provider_execution_not_configured")
            return google_runtime

        def meta() -> MetaResources:
            nonlocal meta_resource
            if meta_source is None or meta_config is None:
                raise HTTPException(409, "provider_execution_not_configured")
            if meta_resource is None:
                evidence = meta_source.build(sessions, authorize, actor, clock)
                if evidence.descriptor != meta_source.descriptor:
                    raise HTTPException(409, "meta_execution_evidence_source_changed")
                transport = meta_execution_transport(meta_config[0])
                stack.callback(transport.close)
                contexts = OwnedMetaContexts(
                    sessions, authorize, actor, meta_config[0], configuration, clock
                )
                stack.callback(contexts.close)
                meta_resource = MetaResources(
                    contexts, OwnedMetaMedia(contexts, media_store()), transport, evidence
                )
            return meta_resource

        def tiktok() -> TikTokResources:
            nonlocal tiktok_resource
            if tiktok_source is None or tiktok_config is None:
                raise HTTPException(409, "provider_execution_not_configured")
            if tiktok_resource is None:
                evidence = tiktok_source.build(sessions, authorize, actor, clock)
                if (
                    evidence.descriptor != tiktok_source.descriptor
                    or evidence.decoded_contract_catalog is None
                    or evidence.descriptor.environment != "contract_test"
                ):
                    raise HTTPException(409, "tiktok_execution_evidence_source_changed")
                transport = tiktok_execution_transport(tiktok_config[0])
                stack.callback(transport.close)
                contexts = OwnedTikTokContexts(
                    sessions, authorize, actor, tiktok_config[0], configuration, clock
                )
                stack.callback(contexts.close)
                tiktok_resource = TikTokResources(
                    contexts, OwnedTikTokMedia(contexts, media_store()), transport, evidence
                )
            return tiktok_resource

        def platform(plan: CreationPlan) -> str:
            value = plan.review.scope.account.platform
            if value not in {"google_ads", "meta_ads", "tiktok_ads"}:
                raise HTTPException(409, "provider_execution_not_configured")
            return value

        def qualify(plan: CreationPlan, now: datetime) -> ConfigurationQualification:
            if platform(plan) == "google_ads":
                return google().creation.qualification_reader(plan, now)
            if platform(plan) == "tiktok_ads":
                if not isinstance(plan, SocialPublishPlan) or tiktok_config is None:
                    raise HTTPException(409, "provider_execution_not_configured")
                return tiktok().evidence.configuration(plan, now)
            if not isinstance(plan, SocialPublishPlan) or meta_config is None:
                raise HTTPException(409, "provider_execution_not_configured")
            if meta_config[0].environment == "live" and plan.review.qualification_blockers:
                raise HTTPException(409, "social_native_configuration_unqualified")
            return meta().evidence.configuration(plan, now)

        def exposure(
            session: Session, binding: ProviderMandateBinding, plan: CreationPlan, now: datetime
        ) -> ExposureEvidence:
            if platform(plan) == "google_ads":
                return google().creation.exposure_reader(session, binding, plan, now)
            if platform(plan) == "tiktok_ads":
                return tiktok().evidence.creation(session, binding, plan, now)
            return meta().evidence.creation(session, binding, plan, now)

        def activation_exposure(
            session: Session,
            binding: ProviderMandateBinding,
            plan: CreationPlan,
            reservation_id: str,
            now: datetime,
        ) -> ExposureEvidence:
            if platform(plan) == "google_ads":
                runtime = google().activation
                if runtime is None:
                    raise HTTPException(409, "activation_not_configured")
                return runtime.review.exposure_reader(session, binding, plan, reservation_id, now)
            if platform(plan) == "tiktok_ads":
                if tiktok_config is None or not tiktok_config[0].activation_enabled:
                    raise HTTPException(409, "activation_not_configured")
                return tiktok().evidence.activation(session, binding, plan, reservation_id, now)
            if meta_config is None or not meta_config[0].activation_enabled:
                raise HTTPException(409, "activation_not_configured")
            return meta().evidence.activation(session, binding, plan, reservation_id, now)

        def google_context(scope: PublicationScope) -> ProviderContext:
            if scope.account.platform != "google_ads":
                raise HTTPException(409, "provider_execution_not_configured")
            return google().google_context(scope)

        def social_context(request: SocialBoundRequest) -> SocialProviderContext:
            if request.scope.account.platform == "tiktok_ads":
                return tiktok().contexts.publication(request)
            if request.scope.account.platform != "meta_ads":
                raise HTTPException(409, "provider_execution_not_configured")
            return meta().contexts.publication(request)

        def activation_context(request: ActivationRequest) -> ActivationContext:
            if request.account.account.platform == "google_ads":
                runtime = google().activation
                if runtime is None:
                    raise HTTPException(409, "activation_not_configured")
                return runtime.context(request)
            if request.account.account.platform == "tiktok_ads":
                if tiktok_config is None or not tiktok_config[0].activation_enabled:
                    raise HTTPException(409, "activation_not_configured")
                return tiktok().contexts.activation(request)
            if request.account.account.platform != "meta_ads":
                raise HTTPException(409, "provider_execution_not_configured")
            if meta_config is None or not meta_config[0].activation_enabled:
                raise HTTPException(409, "activation_not_configured")
            return meta().contexts.activation(request)

        def google_catalog(request: GoogleCatalogRequest, now: datetime) -> GoogleCatalog:
            if request.account.account.platform != "google_ads":
                raise HTTPException(409, "provider_execution_not_configured")
            catalog = google().catalog
            if catalog is None:
                raise HTTPException(409, "provider_execution_not_configured")
            return catalog(request, now)

        def meta_catalog(request: SocialCatalogRequest, now: datetime) -> SocialCatalog:
            if request.account.account.platform == "tiktok_ads":
                resource_t = tiktok()
                resource_t.contexts.catalog(request, now)
                decoded = resource_t.evidence.decoded_contract_catalog
                assert decoded is not None
                result_t = SocialCatalog.model_validate(decoded(request, now).model_dump())
                resource_t.contexts.credentials(request.account)
                if result_t.request != request or not (
                    now <= result_t.observed_at <= clock() < result_t.expires_at
                ):
                    raise HTTPException(409, "tiktok_decoded_catalog_changed")
                return result_t
            if request.account.account.platform != "meta_ads" or meta_config is None:
                raise HTTPException(409, "provider_execution_not_configured")
            resource = meta()
            reader = MetaCatalogHTTP(
                resource.contexts.catalog,
                meta_config[1].profiles,
                transport=_BorrowedTransport(resource.transport),
                clock=clock,
            )
            result = reader(request, now)
            # Recheck original authority/generation after catalog HTTP.
            resource.contexts.credentials(request.account)
            return result

        def current_configuration(document: SocialConfigurationDocument, now: datetime) -> None:
            if document.request.account.account.platform == "tiktok_ads":
                if tiktok_config is None or tiktok_source is None:
                    raise HTTPException(409, "provider_execution_not_configured")
                tiktok().contexts.ensure_current()
                rules_t = {r.profile_digest: r for r in tiktok_config[1].requirements}
                if document.requirements != rules_t.get(document.requirements.profile_digest):
                    raise HTTPException(409, "social_configuration_changed")
                return
            if document.request.account.account.platform != "meta_ads" or meta_config is None:
                raise HTTPException(409, "provider_execution_not_configured")
            rules = {r.profile_digest: r for r in meta_config[1].requirements}
            if document.requirements != rules.get(document.requirements.profile_digest):
                raise HTTPException(409, "social_configuration_changed")

        social = (
            SocialReviewRuntime(
                manifest.environment,
                meta_catalog,
                (meta_config[1].profiles if meta_source and meta_config else ())
                + (tiktok_config[1].profiles if tiktok_source and tiktok_config else ()),
                {
                    r.profile_digest: r
                    for r in (meta_config[1].requirements if meta_source and meta_config else ())
                    + (tiktok_config[1].requirements if tiktok_source and tiktok_config else ())
                },
                clock,
            )
            if meta_source is not None or tiktok_source is not None
            else None
        )
        google_http = LazyGoogleHTTP(google)
        transport, media = LazyMetaTransport(meta), LazyMetaMedia(meta)
        ttransport, tmedia = LazyMetaTransport(tiktok), LazyMetaMedia(tiktok)
        creation = CreationRuntime(
            environment=manifest.environment,
            qualification_reader=qualify,
            exposure_reader=exposure,
            google=google_http,
            meta=MetaPublicationTransport(media, transport=transport),
            tiktok=TikTokPublicationTransport(tmedia, transport=ttransport),
            google_context=lambda request: google_context(request.scope),
            social_context=social_context,
            live_enabled=manifest.live_execution_enabled,
            authorize=authorize,
            social_configuration_current=current_configuration,
        )
        google_activation = GoogleActivationHTTP()
        google_activation.http = google_http
        activation = (
            ActivationRuntime(
                review=ActivationReviewRuntime(creation, activation_exposure),
                google=google_activation,
                meta=MetaActivationHTTP(media, transport=transport),
                tiktok=TikTokActivationHTTP(tmedia, transport=ttransport),
                context=activation_context,
            )
            if (
                (
                    google_source is not None
                    and google_manifest
                    and google_manifest.activation_enabled
                )
                or (meta_source is not None and meta_config and meta_config[0].activation_enabled)
                or (
                    tiktok_source is not None
                    and tiktok_config
                    and tiktok_config[0].activation_enabled
                )
            )
            else None
        )
        yield CustomerExecutionRuntime(
            creation=creation,
            activation=activation,
            google_qualification=google_http,
            google_context=google_context,
            catalog=google_catalog if google_source is not None else None,
            clock=clock,
            social_review=social,
        )
