"""Resumable read contracts. Checkpoints are private, never maturity evidence."""

from datetime import date
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.commerce.evidence import digest
from app.commerce.independent_contracts import ScanLimits, ScanRequest
from app.outcomes.contracts import Digest, Frozen

Id = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
Phase = Literal[
    "authority_before",
    "order_page",
    "agreement_page",
    "sale_page",
    "order_check",
    "authority_after",
    "publish",
]
JobState = Literal["pending", "running", "completed", "unavailable", "cancelled", "expired"]


class AcquisitionProfile(Frozen):
    schema_version: Literal["inlet.acquisition-execution-profile.v1"] = (
        "inlet.acquisition-execution-profile.v1"
    )
    limits: ScanLimits
    poll_interval_seconds: int = Field(strict=True, ge=1, le=60)
    tick_time_budget_seconds: int = Field(strict=True, ge=1, le=30)
    tick_request_budget: int = Field(strict=True, ge=1, le=256)
    tick_workspace_budget: int = Field(strict=True, ge=1, le=100)
    step_io_timeout_seconds: float = Field(gt=0, le=5, allow_inf_nan=False)
    lease_seconds: int = Field(strict=True, ge=10, le=60)
    backoff_seconds: int = Field(strict=True, ge=1, le=300)
    seen_key_limit: int = Field(strict=True, ge=1, le=250_000)

    @model_validator(mode="after")
    def feasible(self) -> "AcquisitionProfile":
        if (
            self.step_io_timeout_seconds > self.tick_time_budget_seconds
            or self.lease_seconds <= self.step_io_timeout_seconds
            or 3 * (self.poll_interval_seconds + self.tick_time_budget_seconds)
            >= self.limits.lifetime_seconds
        ):
            raise ValueError("acquisition_worker_cadence_unavailable")
        return self

    def digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class AcquisitionIntent(Frozen):
    goal_id: Id
    expected_goal_revision: int = Field(strict=True, ge=1)
    start: date
    end: date

    @model_validator(mode="after")
    def bounded(self) -> "AcquisitionIntent":
        if not 0 < (self.end - self.start).days <= 400:
            raise ValueError("acquisition_window_unavailable")
        return self


class PendingOrder(Frozen):
    identity_digest: Digest
    created_at: AwareDatetime
    updated_at: AwareDatetime
    test: bool
    customer_digest: Digest | None


class PendingAgreement(Frozen):
    identity_digest: Digest
    kind: Literal["OrderAgreement", "OrderEditAgreement", "RefundAgreement"]
    reason: Literal["ORDER", "ORDER_EDIT", "REFUND"]
    happened_at: AwareDatetime


class DayTotal(Frozen):
    day: date
    value_micros: int = Field(strict=True, ge=-(10**18), le=10**18)
    entry_count: int = Field(strict=True, ge=0, le=500_000)


class Checkpoint(Frozen):
    schema_version: Literal["inlet.acquisition-checkpoint.v1"] = "inlet.acquisition-checkpoint.v1"
    request_digest: Digest
    profile_digest: Digest
    phase: Phase
    sequence: int = Field(strict=True, ge=0)
    pending_orders: tuple[PendingOrder, ...] = Field(max_length=50)
    agreement: PendingAgreement | None
    order_has_agreement: bool
    orders_more: bool
    agreements_more: bool
    sales_more: bool
    order_nested_requests: int = Field(strict=True, ge=0, le=50)
    orders_enumerated: int = Field(strict=True, ge=0, le=24000)
    agreements_enumerated: int = Field(strict=True, ge=0, le=500_000)
    sales_enumerated: int = Field(strict=True, ge=0, le=500_000)
    committed: tuple[DayTotal, ...] = Field(max_length=400)
    tentative: tuple[DayTotal, ...] = Field(max_length=400)

    @model_validator(mode="after")
    def bounded(self) -> "Checkpoint":
        if len(self.model_dump_json().encode()) > 128 * 1024:
            raise ValueError("acquisition_checkpoint_limit")
        for rows in (self.committed, self.tentative):
            days = [row.day for row in rows]
            if days != sorted(set(days)):
                raise ValueError("acquisition_checkpoint_days_invalid")
        return self

    def digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class NativeHandles(Frozen):
    """Only encrypted at rest. Never include customer IDs or provider bodies."""

    order_ids: tuple[Annotated[str, Field(pattern=r"^gid://shopify/Order/[0-9]{1,24}$")], ...] = (
        Field(max_length=50)
    )
    last_order_number: Annotated[str, Field(pattern=r"^[0-9]{1,24}$")]
    order_cursor: Annotated[str, Field(max_length=4096)] | None
    agreement_cursor: Annotated[str, Field(max_length=4096)] | None
    agreement_next_cursor: Annotated[str, Field(max_length=4096)] | None = None
    sale_cursor: Annotated[str, Field(max_length=4096)] | None
    agreement_id: Annotated[str, Field(max_length=128)] | None


class AcquisitionStatus(Frozen):
    job_id: Id
    state: JobState
    phase: Phase | None
    deadline_at: AwareDatetime
    publication_id: Id | None
    error_code: Annotated[str, Field(pattern=r"^[a-z_]{1,64}$")] | None
    correction_state: Literal["unresolved"] = "unresolved"
    maturity: Literal["unqualified"] = "unqualified"
    spending_authority: Literal["none"] = "none"


def initial_checkpoint(request: ScanRequest, profile: AcquisitionProfile) -> Checkpoint:
    return Checkpoint(
        request_digest=request.request_digest,
        profile_digest=profile.digest(),
        phase="authority_before",
        sequence=0,
        pending_orders=(),
        agreement=None,
        order_has_agreement=False,
        orders_more=False,
        agreements_more=False,
        sales_more=False,
        order_nested_requests=0,
        orders_enumerated=0,
        agreements_enumerated=0,
        sales_enumerated=0,
        committed=(),
        tentative=(),
    )
