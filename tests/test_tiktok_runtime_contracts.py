from pathlib import Path
from typing import Any

import pytest
from app.production_runtime.tiktok_configuration import (
    TikTokConfigurationBundleV1,
    TikTokRuntimeConfigurationError,
    load_tiktok_execution_configuration,
)
from app.production_runtime.tiktok_contracts import (
    RegisteredTikTokEvidenceSource,
    TikTokEvidenceDescriptor,
    TikTokExecutionManifestV1,
    admit_tiktok_source,
)
from app.publication.social_catalog import TikTokConfigurationProfile
from app.publication.social_review_contracts import SocialRequirements
from pydantic import ValidationError


def bundle_document() -> dict[str, Any]:
    profile = TikTokConfigurationProfile(
        profile_id="explicit_fixture",
        label="Fixture Only",
        currency="USD",
        currency_exponent=2,
        location_ids_by_country={"US": ["6252001"]},
        language_codes={"en": "en"},
        age_groups=["AGE_18_24"],
        click_attribution_window="ONE_DAY",
        view_attribution_window="OFF",
        engaged_view_attribution_window="OFF",
        comment_disabled=True,
        share_disabled=True,
        video_download_disabled=True,
    )
    rules = SocialRequirements(
        profile_digest=profile.digest(),
        requirements_digest="b" * 64,
        wording_version="fixture_v1",
        verified=True,
        dsa_required=False,
        wording="Review this exact video and cover. Fixture wording, not production evidence.",
    )
    return {
        "cover_review_required": True,
        "profiles": [profile.model_dump()],
        "requirements": [rules.model_dump()],
    }


def manifest(bundle: TikTokConfigurationBundleV1) -> TikTokExecutionManifestV1:
    return TikTokExecutionManifestV1(
        manifest_id="explicit_fixture",
        revision=1,
        environment="contract_test",
        api_version="v1.3",
        evidence_source_id="scenario_fixture",
        evidence_profile_digest="a" * 64,
        configuration_bundle_digest=bundle.digest(),
        live_execution_enabled=False,
        activation_enabled=True,
        credential_minimum_remaining_seconds=300,
        context_lifetime_seconds=60,
    )


def test_bundle_snapshot_cannot_be_changed_through_nested_original_or_returned_models() -> None:
    original = bundle_document()
    frozen = TikTokConfigurationBundleV1.from_document(original)
    commitment = frozen.digest()
    original["profiles"][0]["language_codes"]["en"] = "changed"
    profiles = frozen.profiles
    profiles[0].language_codes["en"] = "other"
    profiles[0].location_ids_by_country["US"].append("42")
    frozen.requirements[0].wording = "changed"
    assert frozen.digest() == commitment
    assert frozen.profiles[0].language_codes == {"en": "en"}
    assert frozen.profiles[0].location_ids_by_country == {"US": ["6252001"]}
    assert frozen.requirements[0].wording != "changed"


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "foreign", "currency", "cover", "wording"]
)
def test_exact_explicit_profile_rule_pair_required(change: str) -> None:
    value = bundle_document()
    if change == "missing":
        value["requirements"] = []
    elif change == "duplicate":
        value["profiles"] *= 2
    elif change == "foreign":
        value["requirements"][0]["profile_digest"] = "f" * 64
    elif change == "currency":
        value["profiles"][0]["currency"] = "EUR"
        value["requirements"][0]["profile_digest"] = TikTokConfigurationProfile.model_validate(
            value["profiles"][0]
        ).digest()
    elif change == "cover":
        value["cover_review_required"] = False
    else:
        value["requirements"][0]["wording"] = "   "
    with pytest.raises(ValidationError):
        TikTokConfigurationBundleV1.from_document(value)


def test_source_admission_is_pure_and_cannot_promote_scenario() -> None:
    def forbidden(*args: Any) -> Any:
        raise AssertionError("admission must never invoke source")

    value = manifest(TikTokConfigurationBundleV1.from_document(bundle_document()))
    descriptor = TikTokEvidenceDescriptor(
        source_id=value.evidence_source_id,
        profile_digest=value.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )
    source = RegisteredTikTokEvidenceSource(descriptor, forbidden)
    assert admit_tiktok_source(value, None) is None
    assert admit_tiktok_source(value, source) is source
    live = TikTokExecutionManifestV1.model_validate(
        {**value.model_dump(), "environment": "live", "live_execution_enabled": True}
    )
    assert admit_tiktok_source(live, source) is None
    with pytest.raises(ValidationError):
        TikTokEvidenceDescriptor.model_validate({**descriptor.model_dump(), "environment": "live"})
    with pytest.raises(ValidationError):
        TikTokExecutionManifestV1.model_validate(
            {**value.model_dump(), "live_execution_enabled": True}
        )


def test_loader_pins_both_documents_and_rejects_duplicate_keys(tmp_path: Path) -> None:
    import json

    document = bundle_document()
    bundle = TikTokConfigurationBundleV1.from_document(document)
    value = manifest(bundle)
    mp, bp = tmp_path / "manifest.json", tmp_path / "bundle.json"
    mp.write_text(value.model_dump_json())
    bp.write_text(json.dumps(document))
    assert load_tiktok_execution_configuration(str(mp), value.digest(), str(bp)) == (value, bundle)
    assert load_tiktok_execution_configuration(None, None, None) is None
    for raw in ('{"profiles":[],"profiles":[]}', '{"proof":{}}', "x" * 65537):
        bp.write_text(raw)
        with pytest.raises(
            TikTokRuntimeConfigurationError, match="^tiktok_execution_configuration_invalid$"
        ):
            load_tiktok_execution_configuration(str(mp), value.digest(), str(bp))
    bp.write_text(json.dumps(document))
    with pytest.raises(TikTokRuntimeConfigurationError):
        load_tiktok_execution_configuration(str(mp), "f" * 64, str(bp))


def test_real_transport_denies_scenario_before_constructor(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    from app.production_runtime.tiktok_transport import tiktok_execution_transport
    from fastapi import HTTPException

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("real transport constructor must not run")

    monkeypatch.setattr(httpx, "HTTPTransport", forbidden)
    with pytest.raises(HTTPException) as caught:
        tiktok_execution_transport(
            manifest(TikTokConfigurationBundleV1.from_document(bundle_document()))
        )
    assert caught.value.status_code == 409


def test_live_descriptor_does_not_resolve_native_parser_or_construct_source() -> None:
    from app.production_runtime.tiktok_contracts import registered_tiktok_evidence

    value = manifest(TikTokConfigurationBundleV1.from_document(bundle_document()))
    live = TikTokExecutionManifestV1.model_validate(
        {**value.model_dump(), "environment": "live", "live_execution_enabled": True}
    )
    descriptor = TikTokEvidenceDescriptor(
        source_id=value.evidence_source_id,
        profile_digest=value.evidence_profile_digest,
        environment="live",
        kind="qualified_live_source",
    )

    def forbidden(*args: Any) -> Any:
        raise AssertionError("native parser missing: no live factory construction")

    assert admit_tiktok_source(live, RegisteredTikTokEvidenceSource(descriptor, forbidden)) is None
    assert registered_tiktok_evidence(value.evidence_source_id) is None


def test_decoded_fixture_catalog_cannot_be_installed_for_live_source() -> None:
    from app.production_runtime.tiktok_contracts import TikTokExecutionEvidence

    descriptor = TikTokEvidenceDescriptor(
        source_id="live_source",
        profile_digest="a" * 64,
        environment="live",
        kind="qualified_live_source",
    )

    def forbidden(*args: Any) -> Any:
        raise AssertionError("constructing evidence must not invoke readers")

    with pytest.raises(ValueError, match="contract-test only"):
        TikTokExecutionEvidence(descriptor, forbidden, forbidden, forbidden, forbidden)
    scenario = TikTokEvidenceDescriptor(
        source_id="fixture",
        profile_digest="a" * 64,
        environment="contract_test",
        kind="contract_scenario",
    )
    assert (
        TikTokExecutionEvidence(
            scenario, forbidden, forbidden, forbidden, forbidden
        ).decoded_contract_catalog
        is forbidden
    )


def test_reserved_context_is_tiktok_scoped_and_secret_excluded() -> None:
    from datetime import timedelta

    from app.production_runtime.tiktok_contracts import TikTokCatalogContext

    from tests.test_provider_publication_contracts import NOW
    from tests.test_social_customer_catalog import request

    context = TikTokCatalogContext(
        account=request(True).account,
        request_digest=request(True).digest(),
        expires_at=NOW + timedelta(seconds=60),
        access_token="offline-test-secret",
    )
    assert "offline-test-secret" not in repr(context)
    assert "access_token" not in context.model_dump()
    with pytest.raises(ValidationError):
        TikTokCatalogContext(
            account=request().account,
            request_digest=request().digest(),
            expires_at=NOW,
            access_token="offline-test-secret",
        )


@pytest.mark.parametrize("change", ["partial", "extra", "version", "bundle_pin", "oversized"])
def test_loader_rejects_invalid_or_unpinned_configuration(tmp_path: Path, change: str) -> None:
    import json

    document = bundle_document()
    bundle = TikTokConfigurationBundleV1.from_document(document)
    selected = manifest(bundle)
    mp, bp = tmp_path / "manifest.json", tmp_path / "bundle.json"
    value = selected.model_dump()
    if change == "extra":
        value["credentials"] = "forbidden"
    elif change == "version":
        value["api_version"] = "v1.2"
    elif change == "bundle_pin":
        document["requirements"][0]["wording"] = "Changed reviewed video and cover wording"
    mp.write_text("x" * 16385 if change == "oversized" else json.dumps(value))
    bp.write_text(json.dumps(document))
    with pytest.raises(
        TikTokRuntimeConfigurationError, match="^tiktok_execution_configuration_invalid$"
    ):
        load_tiktok_execution_configuration(
            None if change == "partial" else str(mp), selected.digest(), str(bp)
        )


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("source_id", "other_source"),
        ("profile_digest", "f" * 64),
    ],
)
def test_source_identity_mismatch_denies_before_build(field: str, replacement: str) -> None:
    selected = manifest(TikTokConfigurationBundleV1.from_document(bundle_document()))
    values = dict(
        source_id=selected.evidence_source_id,
        profile_digest=selected.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )
    values[field] = replacement
    descriptor = TikTokEvidenceDescriptor.model_validate(values)

    def forbidden(*args: Any) -> Any:
        raise AssertionError("mismatch cannot build evidence")

    assert (
        admit_tiktok_source(selected, RegisteredTikTokEvidenceSource(descriptor, forbidden)) is None
    )
