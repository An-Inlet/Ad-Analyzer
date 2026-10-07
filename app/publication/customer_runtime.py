"""Server-only execution assembly. No credential factory or live activation is installed."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.executors.google_publication import GooglePublicationHTTP
from app.publication.activation import ActivationRuntime
from app.publication.clock import utc_now as utc_now
from app.publication.contracts import PublicationScope
from app.publication.coordinator_contracts import CreationRuntime
from app.publication.customer_catalog import GoogleCatalogReader
from app.publication.provider_contracts import ProviderContext
from app.publication.social_review_runtime import SocialReviewRuntime


@dataclass(frozen=True)
class CustomerExecutionRuntime:
    creation: CreationRuntime
    activation: ActivationRuntime | None
    google_qualification: GooglePublicationHTTP
    google_context: Callable[[PublicationScope], ProviderContext]
    catalog: GoogleCatalogReader | None = None
    clock: Callable[[], datetime] = utc_now
    social_review: SocialReviewRuntime | None = None


def get_customer_execution_runtime() -> CustomerExecutionRuntime | None:
    return None
