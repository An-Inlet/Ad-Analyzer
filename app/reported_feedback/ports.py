"""Frozen owned customer ports. HTTP callers supply intent, never metric/policy proof."""

from typing import Protocol

from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.reported_feedback.contracts import (
    ComparisonIntentV1,
    ComparisonProgressV1,
    FeedbackPreviewIntentV1,
    OperationalReportedComparisonV1,
    ReportedFeedbackPreviewV1,
)
from app.reported_feedback.runtime import ReportedFeedbackRuntime


class RequestComparison(Protocol):
    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        workspace_id: int,
        intent: ComparisonIntentV1,
        runtime: ReportedFeedbackRuntime,
    ) -> ComparisonProgressV1: ...


class ReadComparisonProgress(Protocol):
    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        workspace_id: int,
        request_id: str,
        runtime: ReportedFeedbackRuntime,
    ) -> ComparisonProgressV1: ...


class ReobserveComparison(Protocol):
    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        workspace_id: int,
        request_id: str,
        runtime: ReportedFeedbackRuntime,
    ) -> ComparisonProgressV1: ...


class ReadComparison(Protocol):
    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        workspace_id: int,
        request_id: str,
        runtime: ReportedFeedbackRuntime,
    ) -> OperationalReportedComparisonV1: ...


class ApplyFeedbackPreview(Protocol):
    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        workspace_id: int,
        intent: FeedbackPreviewIntentV1,
        runtime: ReportedFeedbackRuntime,
    ) -> ReportedFeedbackPreviewV1: ...


class ReadFeedbackPreview(Protocol):
    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        workspace_id: int,
        preview_id: str,
        runtime: ReportedFeedbackRuntime,
    ) -> ReportedFeedbackPreviewV1: ...


# These hooks run inside the existing native workspace/source transaction. They
# perform local reads only; the existing Meta client owns subsequent bounded HTTP.
from datetime import datetime  # noqa: E402

from app.ads.models import AdvertisingAccount  # noqa: E402
from app.campaign_performance.models import PerformanceCompletion  # noqa: E402
from app.meta.models import MetaConnection  # noqa: E402
from app.reported_feedback.contracts import (  # noqa: E402
    FixedWindowLeaseV1,
    ReportedWindowCapsuleV1,
)


class ClaimFixedWindow(Protocol):
    def __call__(
        self,
        db: Session,
        source: MetaConnection,
        account: AdvertisingAccount,
        now: datetime,
        runtime: ReportedFeedbackRuntime,
        *,
        rolling_due: bool,
        authorized_job_id: str | None = None,
    ) -> FixedWindowLeaseV1 | None: ...


class CaptureTerminalWindow(Protocol):
    def __call__(
        self,
        db: Session,
        source: MetaConnection,
        completion: PerformanceCompletion,
        lease: FixedWindowLeaseV1,
        now: datetime,
        runtime: ReportedFeedbackRuntime,
    ) -> ReportedWindowCapsuleV1: ...
