from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class CrmEventType(StrEnum):
    LEAD_CREATED = "lead_created"
    APPOINTMENT_SCHEDULED = "appointment_scheduled"
    LEAD_QUALIFIED = "lead_qualified"
    PROPOSAL_SENT = "proposal_sent"
    SALE_WON = "sale_won"
    SALE_LOST = "sale_lost"
    SALE_CANCELLED = "sale_cancelled"
    REVENUE_ADJUSTED = "revenue_adjusted"


class CrmEvent(BaseModel):
    """Strict allowlist for data permitted to cross the CRM security boundary."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    event_type: CrmEventType
    occurred_at: datetime
    crm_lead_id: str = Field(min_length=1, max_length=128)
    crm_opportunity_id: str | None = Field(default=None, max_length=128)
    value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    gclid: str | None = Field(default=None, max_length=256)
    gbraid: str | None = Field(default=None, max_length=256)
    wbraid: str | None = Field(default=None, max_length=256)
    utm_source: str | None = Field(default=None, max_length=256)
    utm_medium: str | None = Field(default=None, max_length=256)
    utm_campaign: str | None = Field(default=None, max_length=256)
    utm_term: str | None = Field(default=None, max_length=256)
    utm_content: str | None = Field(default=None, max_length=256)
    landing_page: HttpUrl | None = None

    @field_validator("occurred_at")
    @classmethod
    def timestamp_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class CrmReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    receipt_id: str
    status: str = "accepted"
