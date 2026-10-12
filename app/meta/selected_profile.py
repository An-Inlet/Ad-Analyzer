"""One documented count-only report; no implicit windows, money or pixel identity."""

import hashlib
import json

from app.campaign_performance.capture_settings import CaptureSettingsV1, no_requested_overrides
from app.campaign_performance.presence_contracts import AttributionBasisV1

PROFILE = "meta.website-purchase-count.campaign-day.v1"
PRODUCER = "meta.v26.campaign-day.website-purchase-count.v1"
EVENT = "offsite_conversion.fb_pixel_purchase"
FIELDS = "account_id,campaign_id,date_start,date_stop,account_currency,actions"


def query_profile_digest() -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "producer": PRODUCER,
                "method": "GET",
                "edge": "advertiser/insights",
                "api": "v26.0",
                "fields": FIELDS,
                "level": "campaign",
                "time_increment": "1",
                "action_breakdowns": ["action_type"],
                "attribution_options": "not_sent",
                "filtering": "not_sent",
                "status_coverage": "not_qualified",
                "event": EVENT,
                "count_cell": "actions.exact_action_type.value",
                "money": "unsupported",
                "omitted": "missing_not_zero",
                "counting_mode": "unknown",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def settings() -> CaptureSettingsV1:
    return CaptureSettingsV1(
        profile=PROFILE,
        report_support="documented_meta_count",
        count_meaning="website_purchase_actions",
        value_unit="unknown",
        requested=no_requested_overrides(),
        effective=AttributionBasisV1(
            click_window_days=None,
            view_window_days=None,
            report_time_basis="unknown",
            provenance="provider_default_unknown",
            producer_contract=PRODUCER,
        ),
    )
