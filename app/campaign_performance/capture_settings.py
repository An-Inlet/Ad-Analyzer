"""Finite original-request settings; no provider capability or attribution inference."""

import hashlib
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.campaign_performance.presence_contracts import AttributionBasisV1, Frozen, _canonical

Profile = Literal[
    "google.conversions.campaign-day.v1",
    "google.all-conversions.campaign-day.v1",
    "meta.website-purchase.campaign-day.v1",
    "meta.website-purchase-count.campaign-day.v1",
    "meta.website-lead.campaign-day.v1",
    "tiktok.website-payment.campaign-day.v1",
]
Window = Literal["1d_click", "7d_click", "28d_click", "1d_view", "7d_view", "28d_view"]


class RequestedAttributionV1(Frozen):
    action_report_time: Literal["impression", "conversion", "mixed"] | None
    use_unified_attribution_setting: Annotated[bool, Field(strict=True)] | None
    action_attribution_windows: tuple[Window, ...] = Field(max_length=6)

    @model_validator(mode="after")
    def unique(self) -> "RequestedAttributionV1":
        if len(set(self.action_attribution_windows)) != len(self.action_attribution_windows):
            raise ValueError("duplicate requested window")
        return self


def no_requested_overrides() -> RequestedAttributionV1:
    return RequestedAttributionV1(
        action_report_time=None,
        use_unified_attribution_setting=None,
        action_attribution_windows=(),
    )


class CaptureSettingsV1(Frozen):
    schema_version: Literal["inlet.capture-settings.v1"] = "inlet.capture-settings.v1"
    profile: Profile
    count_meaning: Literal[
        "selected_action_count", "website_purchase_actions", "website_lead_actions"
    ]
    report_support: Literal[
        "existing_google_contract", "documented_meta_count", "unverified", "unsupported"
    ]
    value_unit: Literal["account_currency_major", "unknown"]
    requested: RequestedAttributionV1
    effective: AttributionBasisV1

    @model_validator(mode="after")
    def coherent(self) -> "CaptureSettingsV1":
        # There is no effective-setting evidence producer in this package. A
        # requested option, ignored flag or unverified label cannot replace one.
        if (
            self.effective.provenance != "provider_default_unknown"
            or self.effective.click_window_days is not None
            or self.effective.view_window_days is not None
            or self.effective.report_time_basis != "unknown"
        ):
            raise ValueError("effective settings evidence unavailable")
        google = self.profile.startswith("google.")
        if google:
            if (
                self.report_support != "existing_google_contract"
                or self.value_unit != "account_currency_major"
                or self.count_meaning != "selected_action_count"
            ):
                raise ValueError("existing Google profile mismatch")
        elif self.profile == "meta.website-purchase-count.campaign-day.v1":
            if (
                self.report_support != "documented_meta_count"
                or self.value_unit != "unknown"
                or self.count_meaning != "website_purchase_actions"
                or self.requested != no_requested_overrides()
            ):
                raise ValueError("bounded Meta count profile mismatch")
        elif (
            self.report_support not in {"unverified", "unsupported"}
            or self.value_unit != "unknown"
            or self.count_meaning
            != (
                "website_lead_actions"
                if self.profile == "meta.website-lead.campaign-day.v1"
                else "website_purchase_actions"
            )
        ):
            raise ValueError("social combination or units unqualified")
        if not self.profile.startswith("meta.") and self.requested != no_requested_overrides():
            raise ValueError("profile does not send Meta attribution options")
        if self.effective.producer_contract != self.producer():
            raise ValueError("settings producer mismatch")
        return self

    def producer(self) -> str:
        if self.profile.startswith("google."):
            return "google.v24.campaign-day.selected-action.v1"
        if self.profile == "meta.website-purchase-count.campaign-day.v1":
            return "meta.v26.campaign-day.website-purchase-count.v1"
        return "unverified." + self.profile

    def query_digest(self) -> str:
        if self.profile.startswith("google."):
            from app.google_connections.selected_presence import query_profile_digest

            return query_profile_digest(
                "conversions"
                if self.profile == "google.conversions.campaign-day.v1"
                else "all_conversions"
            )
        if self.profile == "meta.website-purchase-count.campaign-day.v1":
            from app.meta.selected_profile import query_profile_digest as meta_query_digest

            return meta_query_digest()
        return hashlib.sha256(
            b"inlet.capture-settings-profile.v1\x00" + _canonical(self)
        ).hexdigest()

    def assert_binding(
        self,
        *,
        platform: str,
        api: str,
        event: str,
        family: str,
        owner: str,
        advertiser: str,
        producer: str,
        query_digest: str,
        attribution: AttributionBasisV1,
    ) -> None:
        checked = type(self).model_validate(self)
        profiles = {
            "google.conversions.campaign-day.v1": ("google_ads", "v24", "conversions", None),
            "google.all-conversions.campaign-day.v1": (
                "google_ads",
                "v24",
                "all_conversions",
                None,
            ),
            "meta.website-purchase-count.campaign-day.v1": (
                "meta_ads",
                "v26.0",
                "actions",
                "offsite_conversion.fb_pixel_purchase",
            ),
            "meta.website-purchase.campaign-day.v1": (
                "meta_ads",
                "v26.0",
                "actions",
                "offsite_conversion.fb_pixel_purchase",
            ),
            "meta.website-lead.campaign-day.v1": (
                "meta_ads",
                "v26.0",
                "actions",
                "offsite_conversion.fb_pixel_lead",
            ),
            "tiktok.website-payment.campaign-day.v1": (
                "tiktok_ads",
                "v1.3",
                "event_count",
                "complete_payment",
            ),
        }
        expected = profiles[checked.profile]
        if (
            (platform, api, family) != expected[:3]
            or (expected[3] is not None and event != expected[3])
            or owner != advertiser
            or producer != checked.producer()
            or query_digest != checked.query_digest()
            or attribution != checked.effective
        ):
            raise ValueError("settings request binding mismatch")


def google_capture_settings(family: str, attribution: AttributionBasisV1) -> CaptureSettingsV1:
    if family not in {"conversions", "all_conversions"}:
        raise ValueError("unsupported Google settings family")
    return CaptureSettingsV1(
        profile=(
            "google.conversions.campaign-day.v1"
            if family == "conversions"
            else "google.all-conversions.campaign-day.v1"
        ),
        count_meaning="selected_action_count",
        report_support="existing_google_contract",
        value_unit="account_currency_major",
        requested=no_requested_overrides(),
        effective=attribution,
    )
