import hashlib
import json
from datetime import UTC, datetime
from typing import Self

from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdGroup, AdvertisingAccount, Campaign
from app.measurement.enums import PaidClickIdKind, WebAnalyticsSource, WebDeviceCategory
from app.measurement.identifiers import identifier_digest
from app.measurement.models import WebAnalyticsEvent
from app.workspaces.models import Workspace
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

_OPAQUE_IDENTIFIER = r"^[A-Za-z0-9._:-]+$"


class Ga4EventCreate(BaseModel):
    """Allowlisted fields accepted from a future read-only GA4 BigQuery adapter."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    workspace_id: int = Field(ge=1)
    external_event_id: str = Field(min_length=1, max_length=128, pattern=_OPAQUE_IDENTIFIER)
    event_name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    occurred_at: datetime
    user_pseudo_id: str = Field(min_length=1, max_length=128, pattern=_OPAQUE_IDENTIFIER)
    session_id: str = Field(min_length=1, max_length=128, pattern=_OPAQUE_IDENTIFIER)
    analytics_pseudonymous_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        pattern=_OPAQUE_IDENTIFIER,
    )
    gclid: str | None = Field(
        default=None, min_length=1, max_length=256, pattern=_OPAQUE_IDENTIFIER
    )
    gbraid: str | None = Field(
        default=None, min_length=1, max_length=256, pattern=_OPAQUE_IDENTIFIER
    )
    wbraid: str | None = Field(
        default=None, min_length=1, max_length=256, pattern=_OPAQUE_IDENTIFIER
    )
    account_id: int | None = Field(default=None, ge=1)
    campaign_id: int | None = Field(default=None, ge=1)
    ad_group_id: int | None = Field(default=None, ge=1)
    source: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[A-Za-z0-9._+()-]+$",
    )
    medium: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[A-Za-z0-9._+()-]+$",
    )
    device_category: WebDeviceCategory = WebDeviceCategory.OTHER
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    region_code: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    landing_page_path: str | None = Field(default=None, max_length=1024)
    is_paid_touchpoint: bool = False

    @field_validator("occurred_at")
    @classmethod
    def timestamp_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value.astimezone(UTC)

    @field_validator("source", "medium")
    @classmethod
    def normalize_traffic_dimension(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None

    @field_validator("landing_page_path")
    @classmethod
    def landing_page_must_be_path_only(cls, value: str | None) -> str | None:
        if value is not None and (
            not value.startswith("/") or "?" in value or "#" in value or "@" in value
        ):
            raise ValueError("landing_page_path must be a query-free path")
        return value

    @model_validator(mode="after")
    def validate_attribution_shape(self) -> Self:
        click_ids = [value for value in (self.gclid, self.gbraid, self.wbraid) if value]
        if len(click_ids) > 1:
            raise ValueError("only one paid click identifier is allowed")
        if self.campaign_id is not None and self.account_id is None:
            raise ValueError("campaign_id requires account_id")
        if self.ad_group_id is not None and self.campaign_id is None:
            raise ValueError("ad_group_id requires campaign_id")
        if self.is_paid_touchpoint and (
            self.account_id is None or self.campaign_id is None
        ):
            raise ValueError("paid touchpoints require an account and campaign")
        return self


def _click_identifier(event: Ga4EventCreate) -> tuple[PaidClickIdKind | None, str | None]:
    for kind in PaidClickIdKind:
        value = getattr(event, kind.value)
        if value is not None:
            return kind, value
    return None, None


def _event_values(event: Ga4EventCreate) -> dict[str, object]:
    click_kind, click_value = _click_identifier(event)
    values: dict[str, object] = {
        "workspace_id": event.workspace_id,
        "source_system": WebAnalyticsSource.GA4.value,
        "external_event_id": event.external_event_id,
        "event_name": event.event_name,
        "occurred_at": event.occurred_at,
        "user_pseudo_id_digest": identifier_digest(
            event.workspace_id, "ga4_user", event.user_pseudo_id
        ),
        "subject_id_digest": identifier_digest(
            event.workspace_id,
            "subject",
            event.analytics_pseudonymous_id,
        ),
        "session_id_digest": identifier_digest(
            event.workspace_id,
            "ga4_session",
            f"{event.user_pseudo_id}:{event.session_id}",
        ),
        "click_id_kind": click_kind.value if click_kind is not None else None,
        "click_id_digest": identifier_digest(
            event.workspace_id,
            f"paid_click:{click_kind.value}" if click_kind is not None else "paid_click",
            click_value,
        ),
        "account_id": event.account_id,
        "campaign_id": event.campaign_id,
        "ad_group_id": event.ad_group_id,
        "source": event.source,
        "medium": event.medium,
        "device_category": event.device_category.value,
        "country_code": event.country_code,
        "region_code": event.region_code,
        "landing_page_path": event.landing_page_path,
        "is_paid_touchpoint": event.is_paid_touchpoint,
    }
    fingerprint_payload = {}
    for key, value in values.items():
        if key == "external_event_id" or (key == "ad_group_id" and value is None):
            continue
        fingerprint_payload[key] = value.isoformat() if isinstance(value, datetime) else value
    values["event_fingerprint"] = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return values


class WebAnalyticsRepository:
    """Idempotently stores normalized GA4 events without external network access."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record_ga4_event(self, event: Ga4EventCreate) -> tuple[WebAnalyticsEvent, bool]:
        self._validate_scope(event)
        values = _event_values(event)
        existing = self.session.scalar(
            select(WebAnalyticsEvent).where(
                WebAnalyticsEvent.workspace_id == event.workspace_id,
                WebAnalyticsEvent.source_system == WebAnalyticsSource.GA4.value,
                WebAnalyticsEvent.external_event_id == event.external_event_id,
            )
        )
        if existing is not None:
            if existing.event_fingerprint != values["event_fingerprint"]:
                raise ValueError("conflicting web analytics event")
            return existing, False
        record = WebAnalyticsEvent(**values)
        self.session.add(record)
        self.session.flush()
        return record, True

    def _validate_scope(self, event: Ga4EventCreate) -> None:
        if self.session.get(Workspace, event.workspace_id) is None:
            raise ValueError("workspace not found")
        if event.account_id is None:
            return
        account = self.session.get(AdvertisingAccount, event.account_id)
        if account is None or account.workspace_id != event.workspace_id:
            raise ValueError("advertising account is outside the workspace")
        if account.platform != AdvertisingPlatform.GOOGLE_ADS:
            raise ValueError("web analytics touchpoint requires a Google Ads account")
        if event.campaign_id is None:
            return
        campaign = self.session.get(Campaign, event.campaign_id)
        if campaign is None or campaign.account_id != account.id:
            raise ValueError("campaign is outside the advertising account")
        if event.ad_group_id is None:
            return
        ad_group = self.session.get(AdGroup, event.ad_group_id)
        if ad_group is None or ad_group.campaign_id != campaign.id:
            raise ValueError("ad group is outside the campaign")
