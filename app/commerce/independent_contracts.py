"""Server-only independent acquisition; never operational maturity or finality."""

from collections.abc import Callable
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, SecretStr, model_validator

from app.commerce.evidence import digest
from app.outcomes.contracts import Digest, Frozen, Positive
from app.outcomes.maturity import MaturityScope, ReconciledDay


class ScanRequest(Frozen):
    schema_version: Literal["inlet.independent-acquisition-request.v1"] = (
        "inlet.independent-acquisition-request.v1"
    )
    acquisition_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    scope: MaturityScope
    connection_id: Positive
    connection_version: str = Field(min_length=1, max_length=128)
    export_privacy_revision: int = Field(strict=True, ge=0)
    start: date
    end: date

    @model_validator(mode="after")
    def bounded(self) -> "ScanRequest":
        ZoneInfo(self.scope.time_zone)
        if not 0 < (self.end - self.start).days <= 400:
            raise ValueError("invalid acquisition window")
        return self

    @property
    def request_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class ScanPermit(Frozen):
    """Fresh server authority. Adapter must recheck original session and privacy.

    No default authority reader exists. Secret and external identity fields must
    never be persisted in a completion or emitted through a customer endpoint.
    """

    request_digest: Digest
    expires_at: AwareDatetime
    shop_domain: str = Field(exclude=True, repr=False)
    shop_id: str | None = Field(
        default=None, pattern=r"^gid://shopify/Shop/[0-9]{1,24}$", exclude=True, repr=False
    )
    shop_key: Digest = Field(exclude=True, repr=False)
    token: SecretStr = Field(exclude=True, repr=False)
    identifier_key: SecretStr = Field(exclude=True, repr=False)
    active: bool
    privacy_resolved: bool


class ScanLimits(Frozen):
    orders: int = Field(default=2000, strict=True, ge=1, le=24000)
    requests: int = Field(default=10000, strict=True, ge=2, le=10000)
    nested_requests_per_order: int = Field(default=50, strict=True, ge=1, le=50)
    response_bytes: int = Field(default=2 * 1024 * 1024, strict=True, ge=1, le=2 * 1024 * 1024)
    total_bytes: int = Field(default=128 * 1024 * 1024, strict=True, ge=1, le=128 * 1024 * 1024)
    lifetime_seconds: int = Field(default=1800, strict=True, ge=1, le=1800)


class ScanCompletion(Frozen):
    schema_version: Literal["inlet.independent-acquisition.v1"] = "inlet.independent-acquisition.v1"
    request: ScanRequest
    source_api_version: Literal["2026-07"] = "2026-07"
    acquisition: Literal["independent_full_history_enumeration"] = (
        "independent_full_history_enumeration"
    )
    started_at: AwareDatetime
    completed_at: AwareDatetime
    orders_enumerated: int = Field(strict=True, ge=0)
    agreements_enumerated: int = Field(strict=True, ge=0)
    sales_enumerated: int = Field(strict=True, ge=0)
    requests_completed: Positive
    response_bytes: int = Field(strict=True, ge=0)
    days: tuple[ReconciledDay, ...] = Field(min_length=1, max_length=400)
    # Enumeration proves acquisition, not a globally consistent provider snapshot.
    correction_state: Literal["unresolved"] = "unresolved"
    snapshot_consistency: Literal["unavailable"] = "unavailable"
    maturity: Literal["unqualified"] = "unqualified"
    authoritative_finality: Literal["unavailable"] = "unavailable"
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def coherent(self) -> "ScanCompletion":
        if self.completed_at < self.started_at:
            raise ValueError("invalid acquisition interval")
        expected = (self.request.end - self.request.start).days
        if len(self.days) != expected or any(
            item.day.toordinal() != self.request.start.toordinal() + index
            or item.state != "complete"
            for index, item in enumerate(self.days)
        ):
            raise ValueError("incomplete acquisition days")
        return self

    @property
    def completion_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class ScanUnavailable(RuntimeError):
    """Fixed diagnostic code, no provider body or source identities."""

    def __init__(self, code: str, *, retry_after: int | None = None) -> None:
        self.code = code
        self.retry_after = max(1, min(retry_after, 3600)) if retry_after is not None else None
        super().__init__(code)


ScanAuthority = Callable[[ScanRequest, datetime], ScanPermit]
