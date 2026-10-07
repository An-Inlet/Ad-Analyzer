"""Request-owned discovery assembly using the existing TikTok source/transport fences."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.collectors import tiktok_customer_discovery as display
from app.collectors.tiktok_customer_discovery_contracts import (
    TikTokDiscoveryIntentV1,
    TikTokDiscoveryViewV1,
)
from app.collectors.tiktok_owned_discovery import TikTokOwnedDiscovery
from app.production_runtime import assembly, provider_composition
from app.production_runtime.owned_tiktok_contexts import OwnedTikTokContexts
from app.production_runtime.tiktok_configuration import TikTokRuntimeConfigurationError
from app.production_runtime.tiktok_contracts import admit_tiktok_source
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount
from app.settings import Settings


def read_configured_discovery(
    db: Session,
    authorize: ExecutionAuthorizer,
    actor: str,
    configuration: Settings,
    scope: ExecutionAccount,
    intent: TikTokDiscoveryIntentV1,
) -> TikTokDiscoveryViewV1:
    try:
        configured = provider_composition.pinned_tiktok(
            configuration.tiktok_execution_manifest_path,
            configuration.tiktok_execution_manifest_digest,
            configuration.tiktok_execution_bundle_path,
        )
    except TikTokRuntimeConfigurationError:
        raise HTTPException(503, "TikTok discovery is not available right now.") from None
    if configured is None:
        return display.unavailable(intent, "discovery_not_available")
    manifest = configured[0]
    if (
        admit_tiktok_source(
            manifest,
            provider_composition.registered_tiktok_evidence(
                manifest.evidence_source_id,
            ),
        )
        is None
    ):
        return display.unavailable(intent, "discovery_not_available")
    clock = assembly.execution_clock
    engine = db.get_bind()
    contexts = OwnedTikTokContexts(
        lambda: Session(engine),
        authorize,
        actor,
        manifest,
        configuration,
        clock,
    )

    def reader() -> TikTokOwnedDiscovery:
        transport = provider_composition.tiktok_execution_transport(manifest)
        try:
            # Collector performs the concrete MockTransport runtime check. No cast
            # changes that explicit live-network boundary.
            import httpx

            if not isinstance(transport, httpx.MockTransport):
                raise HTTPException(409, "TikTok discovery is not available right now.")
            return TikTokOwnedDiscovery(scope, contexts, transport, clock)
        except Exception:
            transport.close()
            raise

    try:
        original_token, original_expiry = contexts.credentials(scope)

        def original_context() -> None:
            current_token, current_expiry = contexts.credentials(scope)
            if current_token != original_token or clock() >= min(original_expiry, current_expiry):
                raise HTTPException(409, "TikTok discovery context changed. Refresh and try again.")

        identities = reader().identities(intent.identity_type)
        original_context()
        pixels = reader().pixels()
        result = display.project(intent, identities, pixels)
        original_context()
        if (
            admit_tiktok_source(
                manifest,
                provider_composition.registered_tiktok_evidence(
                    manifest.evidence_source_id,
                ),
            )
            is None
        ):
            raise HTTPException(409, "TikTok discovery is not available right now.")
        return result
    finally:
        contexts.close()
