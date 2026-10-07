"""Frozen callable contracts; implementation modules are capture/calibration/preview.

Not injectable browser fact providers. Concrete implementations own validation and
persistence. All native provider IO belongs outside database transactions.
"""

from typing import Protocol

from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.initial_planning.contracts import (
    CalibrationReportV1,
    EfficiencyObjectiveV1,
    InitialPreviewV1,
    ObservationV1,
    PreviewIntentV1,
)
from app.initial_planning.preview_v2 import InitialPreviewV2
from app.initial_planning.runtime import InitialPlanningRuntime


class CaptureCurrent(Protocol):
    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        workspace_id: int,
        account_id: int,
        campaign_id: int,
        runtime: InitialPlanningRuntime,
    ) -> ObservationV1: ...


class RunCalibration(Protocol):
    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        objective: EfficiencyObjectiveV1,
        runtime: InitialPlanningRuntime,
    ) -> CalibrationReportV1: ...


class ReadCalibration(Protocol):
    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        workspace_id: int,
        calibration_id: str,
        runtime: InitialPlanningRuntime,
    ) -> CalibrationReportV1: ...


class PreparePreview(Protocol):
    def __call__(
        self,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        intent: PreviewIntentV1,
        runtime: InitialPlanningRuntime,
    ) -> InitialPreviewV1: ...


class ReadPreview(Protocol):
    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        workspace_id: int,
        preview_id: str,
        runtime: InitialPlanningRuntime,
    ) -> InitialPreviewV1 | InitialPreviewV2: ...
