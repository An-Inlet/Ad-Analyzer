"""Configuration gate: never opens sockets while selecting a transport."""

from app.customer_context.http import (
    CRMReadError,
    HubSpotHTTPRead,
    KlaviyoHTTPRead,
    OmnisendHTTPRead,
)
from app.customer_context.wire import KLAVIYO_REVISION, OMNISEND_REVISION
from app.settings import settings
from app.sources.contracts import ProviderName, SourceTransport, UnavailableSource


def crm_transport(provider: ProviderName) -> SourceTransport:
    try:
        if (
            provider == "klaviyo"
            and settings.klaviyo_runtime_mode == "provider_read"
            and settings.klaviyo_client_secret is not None
            and settings.klaviyo_api_revision == KLAVIYO_REVISION
        ):
            return KlaviyoHTTPRead(settings.klaviyo_client_id, settings.klaviyo_client_secret)
        if (
            provider == "hubspot"
            and settings.hubspot_runtime_mode == "provider_read"
            and settings.hubspot_client_secret is not None
        ):
            return HubSpotHTTPRead(settings.hubspot_client_id, settings.hubspot_client_secret)
        if (
            provider == "omnisend"
            and settings.omnisend_runtime_mode == "provider_read"
            and settings.omnisend_client_secret is not None
            and settings.omnisend_api_revision == OMNISEND_REVISION
        ):
            return OmnisendHTTPRead(settings.omnisend_client_id, settings.omnisend_client_secret)
    except (ValueError, CRMReadError):
        pass
    return UnavailableSource()
