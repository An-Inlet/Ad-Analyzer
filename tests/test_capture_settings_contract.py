"""Exact request/effective separation, explicit wire versions and legacy commitments."""

import hashlib
import json
from pathlib import Path

import pytest
from app.campaign_performance import selected_contracts as contracts
from app.campaign_performance.capture_settings import (
    CaptureSettingsV1,
    google_capture_settings,
    no_requested_overrides,
)
from app.campaign_performance.presence_contracts import AttributionBasisV1, _canonical
from app.campaign_performance.selected_contracts import (
    CustomerEventSelectionV1,
    SelectedCaptureRequestV1,
    SelectedCaptureV1,
    capture_request_digest,
    selected_capture_digest,
    selection_digest,
)
from app.planning_documents.documents import PlanVersion
from app.planning_documents.selected_observation_provenance import selected_observation_provenance
from app.planning_documents.storage import document_for_row, export_row

from tests.test_plan_provenance_version_boundary import row

FIXTURES = Path("tests/fixtures/selected_provenance")


def legacy() -> SelectedCaptureV1:
    return SelectedCaptureV1.model_validate_json(
        (FIXTURES / "pre-settings-capture-v1.json").read_text()
    )


def enriched() -> SelectedCaptureV1:
    body = legacy().model_dump(mode="json")
    request = body["request"]
    request["schema_version"] = "inlet.selected-capture-request.v2"
    # New synthetic profile fixture; never alter or enrich the historical fixture on read.
    from app.google_connections.selected_presence import PRODUCER, query_profile_digest

    request["producer_contract"] = request["attribution"]["producer_contract"] = PRODUCER
    request["query_profile_digest"] = query_profile_digest(request["selection"]["metric_family"])
    request["selection"]["query_profile_digest"] = request["query_profile_digest"]
    request["selection_digest"] = selection_digest(
        CustomerEventSelectionV1.model_validate(request["selection"])
    )
    request["settings"] = google_capture_settings(
        request["selection"]["metric_family"],
        AttributionBasisV1.model_validate(request["attribution"]),
    ).model_dump(mode="json")
    body["schema_version"] = "inlet.selected-capture.v2"
    body["request_digest"] = capture_request_digest(
        SelectedCaptureRequestV1.model_validate(request)
    )
    for fact in body["facts"]:
        fact["request_digest"] = body["request_digest"]
    return SelectedCaptureV1.model_validate(body)


def social(profile: str = "meta.website-purchase.campaign-day.v1") -> CaptureSettingsV1:
    return CaptureSettingsV1.model_validate(
        dict(
            profile=profile,
            count_meaning="website_lead_actions"
            if "lead" in profile
            else "website_purchase_actions",
            report_support="unverified",
            value_unit="unknown",
            requested=no_requested_overrides(),
            effective=dict(
                click_window_days=None,
                view_window_days=None,
                report_time_basis="unknown",
                provenance="provider_default_unknown",
                producer_contract="unverified." + profile,
            ),
        )
    )


def test_genuine_prechange_payloads_and_digests_stay_exact() -> None:
    raw = (FIXTURES / "pre-settings-capture-v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "0284b8fe5cc052d6e4e8266fd76169e840add9e3aa76dcbddfe8cbf78abf87e5"
    )
    capture = legacy()
    assert capture.model_dump(mode="json") == json.loads(raw)
    assert selected_capture_digest(capture) == (
        "6b4b05bb67b8e5c6fc2542b8412994f62ea3a659ca81a784efbe4de10b1fc5c7"
    )
    assert (
        capture.request_digest == "a509831fa064698a9d9e425935d89e90133faee23ae41d5e4cf2976c8876756c"
    )
    assert "settings" not in capture.request.model_dump()
    assert capture.request.model_dump(include={"settings"}) == {}
    assert "settings" not in selected_observation_provenance(capture).model_dump()
    raw = (FIXTURES / "pre-settings-plan-v2.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "985d11878794728b87f46919b8e3fcb0df79b28982ab9845de22fc1e79d4e164"
    )
    document = PlanVersion.model_validate_json(raw)
    assert document.digest() == "2eaa8995eb614e5a1320090f85dd75d794de4dbde3020c584044e24aaac96eae"
    stored = row(document)
    assert document_for_row("planning_document_versions", stored).model_dump(mode="json") == (
        json.loads(raw)
    )
    assert export_row("planning_document_versions", stored)["document"] == json.loads(raw)


@pytest.mark.parametrize("attack", ["request1", "capture1", "request99", "missing", "effective"])
def test_version_and_effective_mismatch_refused(attack: str) -> None:
    body = enriched().model_dump(mode="json")
    if attack == "capture1":
        body["schema_version"] = "inlet.selected-capture.v1"
    elif attack == "missing":
        body["request"].pop("settings")
    elif attack == "effective":
        body["request"]["attribution"].update(
            provenance="verified_request_contract", report_time_basis="conversion"
        )
    else:
        body["request"]["schema_version"] = "inlet.selected-capture-request.v" + (
            "1" if attack == "request1" else "99"
        )
    with pytest.raises(ValueError):
        SelectedCaptureV1.model_validate(body)


@pytest.mark.parametrize("attack", ["profile", "producer", "digest", "event", "family", "owner"])
def test_settings_bind_exact_request(attack: str) -> None:
    body = enriched().request.model_dump(mode="json")
    if attack == "profile":
        body["settings"]["profile"] = "google.all-conversions.campaign-day.v1"
    elif attack in {"producer", "digest"}:
        body["producer_contract" if attack == "producer" else "query_profile_digest"] = (
            "unrelated.v1" if attack == "producer" else "f" * 64
        )
    else:
        choice = body["selection"]
        if attack == "event":
            choice["native_event_id"] = "purchase"
        elif attack == "owner":
            choice["native_event_owner_id"] = "9999999999"
        else:
            choice["metric_family"] = "all_conversions"
    with pytest.raises(ValueError):
        SelectedCaptureRequestV1.model_validate(body)


@pytest.mark.parametrize(
    "profile",
    [
        "meta.website-purchase.campaign-day.v1",
        "meta.website-lead.campaign-day.v1",
        "tiktok.website-payment.campaign-day.v1",
    ],
)
def test_social_profiles_cannot_claim_supported_combination_or_units(profile: str) -> None:
    settings = social(profile)
    assert settings.report_support == "unverified" and settings.value_unit == "unknown"
    for changes in (
        {"report_support": "existing_google_contract"},
        {"value_unit": "account_currency_major"},
        {"profile": "omni_purchase"},
    ):
        with pytest.raises(ValueError):
            CaptureSettingsV1.model_validate(settings.model_copy(update=changes))


def test_meta_requested_ignored_and_retired_options_never_effective() -> None:
    settings = social().model_dump(mode="json")
    settings["requested"] = dict(
        action_report_time="conversion",
        use_unified_attribution_setting=True,
        action_attribution_windows=["7d_click", "7d_view", "28d_view"],
    )
    value = CaptureSettingsV1.model_validate(settings)
    assert (
        value.effective.report_time_basis == "unknown" and value.effective.click_window_days is None
    )
    for provenance in ("verified_request_contract", "observed_response"):
        bad = value.model_copy(
            update={
                "effective": value.effective.model_copy(
                    update={
                        "provenance": provenance,
                        "report_time_basis": "conversion",
                        "click_window_days": 7,
                    }
                )
            }
        )
        with pytest.raises(ValueError, match="effective settings evidence unavailable"):
            CaptureSettingsV1.model_validate(bad)
    google = enriched().request.settings
    assert google is not None
    with pytest.raises(ValueError, match="does not send Meta"):
        CaptureSettingsV1.model_validate(google.model_copy(update={"requested": value.requested}))


def test_unverified_capture_cannot_hold_present_count_or_money() -> None:
    body = enriched().model_dump(mode="json")
    req = body["request"]
    settings = social()
    req["aggregate"]["scope"].update(platform="meta_ads", source_connection_ref="17")
    req["selection"].update(
        scope=req["aggregate"]["scope"],
        event_namespace="meta_action_type",
        native_event_id="offsite_conversion.fb_pixel_purchase",
        metric_family="actions",
        api_version="v26.0",
        query_profile_digest=settings.query_digest(),
    )
    req.update(
        settings=settings.model_dump(mode="json"),
        attribution=settings.effective.model_dump(),
        producer_contract=settings.producer(),
        query_profile_digest=settings.query_digest(),
        selection_digest=selection_digest(
            CustomerEventSelectionV1.model_validate(req["selection"])
        ),
    )
    body["request_digest"] = capture_request_digest(SelectedCaptureRequestV1.model_validate(req))
    for fact in body["facts"]:
        fact["request_digest"] = body["request_digest"]
    with pytest.raises(ValueError, match="unverified report combination"):
        SelectedCaptureV1.model_validate(body)
    body["capability"] = "unknown"
    with pytest.raises(ValueError, match="unknown value units|unqualified selected capability"):
        SelectedCaptureV1.model_validate(body)
    for fact in body["facts"]:
        for field in ("selected_conversions", "selected_value_micros"):
            fact[field] = dict(presence="legacy_unknown", value=None)
    value = SelectedCaptureV1.model_validate(body)
    assert value.capability == "unknown"
    assert selected_observation_provenance(value).settings == settings


def test_request_byte_bound_includes_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    request = enriched().request
    assert contracts.MAX_SELECTED_HEADER_BYTES == 8192
    measured = len(_canonical(request))
    assert measured < 8192 and measured > len(_canonical(legacy().request))
    monkeypatch.setattr(contracts, "MAX_SELECTED_HEADER_BYTES", measured)
    assert SelectedCaptureRequestV1.model_validate(request) == request
    monkeypatch.setattr(contracts, "MAX_SELECTED_HEADER_BYTES", measured - 1)
    with pytest.raises(ValueError, match="byte capacity"):
        SelectedCaptureRequestV1.model_validate(request)


def test_prior_capture_reader_refuses_new_tag_and_settings(tmp_path: Path) -> None:
    import subprocess
    import sys

    source = FIXTURES / "pre-settings-selected-contracts.py.txt"
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == "b9a2ebe0cac22fcca7fa3ac61bd8d944d2e9f0926f03aa065522755662853614"
    )
    payload = tmp_path / "new-capture.json"
    payload.write_text(enriched().model_dump_json())
    script = tmp_path / "prior_reader.py"
    script.write_text("""
import json,sys,types
from pathlib import Path
root=Path(sys.argv[1]); fixtures=root/'tests/fixtures/selected_provenance'
name='app.campaign_performance.selected_contracts'
module=types.ModuleType(name);sys.modules[name]=module
source=fixtures/'pre-settings-selected-contracts.py.txt'
exec(compile(source.read_text(),str(source),'exec'),module.__dict__)
legacy=json.loads((fixtures/'pre-settings-capture-v1.json').read_text())
assert module.SelectedCaptureV1.model_validate(legacy).model_dump(mode='json')==legacy
new=json.loads(Path(sys.argv[2]).read_text())
for payload in (new,{**new,'schema_version':'inlet.selected-capture.v1'}):
    try:module.SelectedCaptureV1.model_validate(payload)
    except ValueError:pass
    else:raise AssertionError('old reader admitted new settings')
print('PASS old v1 exact; request/capture2 refused')
""")
    result = subprocess.run(
        [sys.executable, str(script), str(Path.cwd()), str(payload)],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PASS old v1 exact; request/capture2 refused"
