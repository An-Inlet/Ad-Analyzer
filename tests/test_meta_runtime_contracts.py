from pathlib import Path
from typing import Any

import pytest
from app.production_runtime.meta_configuration import (
    MetaConfigurationBundleV1,
    MetaRuntimeConfigurationError,
    load_meta_execution_configuration,
)
from app.production_runtime.meta_contracts import (
    MetaEvidenceDescriptor,
    MetaExecutionManifestV1,
    RegisteredMetaEvidenceSource,
    admit_meta_source,
)
from app.publication.social_catalog import MetaConfigurationProfile
from app.publication.social_contracts import MetaAttribution
from app.publication.social_review_contracts import SocialRequirements
from pydantic import ValidationError


def bundle_document() -> dict[str, Any]:
    profile = MetaConfigurationProfile(
        profile_id="explicit_fixture",
        label="Fixture Only",
        currency="USD",
        currency_exponent=2,
        language_locale_ids={"en": 6},
        attribution=[MetaAttribution(event_type="CLICK_THROUGH", window_days=1)],
        age_min=18,
        age_max=65,
        dsa_required=False,
        url_tags="",
    )
    rules = SocialRequirements(
        profile_digest=profile.digest(),
        requirements_digest="b" * 64,
        wording_version="fixture_v1",
        verified=True,
        dsa_required=False,
        wording="Explicit fixture declaration wording; not production rule evidence.",
    )
    return {"profiles": [profile.model_dump()], "requirements": [rules.model_dump()]}


def manifest(bundle: MetaConfigurationBundleV1) -> MetaExecutionManifestV1:
    return MetaExecutionManifestV1(
        manifest_id="explicit_fixture",
        revision=1,
        environment="contract_test",
        api_version="v26.0",
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
    frozen = MetaConfigurationBundleV1.from_document(original)
    commitment = frozen.digest()
    original["profiles"][0]["language_locale_ids"]["en"] = 99
    profiles = frozen.profiles
    profiles[0].language_locale_ids["en"] = 88
    profiles[0].attribution[0].window_days = 7
    frozen.requirements[0].wording = "changed"
    assert frozen.digest() == commitment
    assert frozen.profiles[0].language_locale_ids == {"en": 6}
    assert frozen.profiles[0].attribution[0].window_days == 1
    assert frozen.requirements[0].wording != "changed"


@pytest.mark.parametrize("change", ["missing", "duplicate", "foreign", "currency", "dsa"])
def test_exact_explicit_profile_rule_pair_required(change: str) -> None:
    value = bundle_document()
    if change == "missing":
        value["requirements"] = []
    elif change == "duplicate":
        value["profiles"] *= 2
    elif change == "foreign":
        value["requirements"][0]["profile_digest"] = "f" * 64
    else:
        field, replacement = ("currency", "EUR") if change == "currency" else ("dsa_required", True)
        value["profiles"][0][field] = replacement
        value["requirements"][0]["profile_digest"] = MetaConfigurationProfile.model_validate(
            value["profiles"][0]
        ).digest()
    with pytest.raises(ValidationError):
        MetaConfigurationBundleV1.from_document(value)


def test_source_admission_is_pure_and_cannot_promote_scenario() -> None:
    def forbidden(*args: Any) -> Any:
        raise AssertionError("admission must never invoke source")

    value = manifest(MetaConfigurationBundleV1.from_document(bundle_document()))
    descriptor = MetaEvidenceDescriptor(
        source_id=value.evidence_source_id,
        profile_digest=value.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )
    source = RegisteredMetaEvidenceSource(descriptor, forbidden)
    assert admit_meta_source(value, None) is None
    assert admit_meta_source(value, source) is source
    live = MetaExecutionManifestV1.model_validate(
        {**value.model_dump(), "environment": "live", "live_execution_enabled": True}
    )
    assert admit_meta_source(live, source) is None
    with pytest.raises(ValidationError):
        MetaEvidenceDescriptor.model_validate({**descriptor.model_dump(), "environment": "live"})
    with pytest.raises(ValidationError):
        MetaExecutionManifestV1.model_validate(
            {**value.model_dump(), "live_execution_enabled": True}
        )


def test_loader_pins_both_documents_and_rejects_duplicate_keys(tmp_path: Path) -> None:
    import json

    document = bundle_document()
    bundle = MetaConfigurationBundleV1.from_document(document)
    value = manifest(bundle)
    mp, bp = tmp_path / "manifest.json", tmp_path / "bundle.json"
    mp.write_text(value.model_dump_json())
    bp.write_text(json.dumps(document))
    assert load_meta_execution_configuration(str(mp), value.digest(), str(bp)) == (value, bundle)
    assert load_meta_execution_configuration(None, None, None) is None
    for raw in ('{"profiles":[],"profiles":[]}', '{"proof":{}}', "x" * 65537):
        bp.write_text(raw)
        with pytest.raises(
            MetaRuntimeConfigurationError, match="^meta_execution_configuration_invalid$"
        ):
            load_meta_execution_configuration(str(mp), value.digest(), str(bp))
    bp.write_text(json.dumps(document))
    with pytest.raises(MetaRuntimeConfigurationError):
        load_meta_execution_configuration(str(mp), "f" * 64, str(bp))


def test_real_transport_denies_scenario_before_constructor(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    from app.production_runtime.meta_transport import meta_execution_transport
    from fastapi import HTTPException

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("real transport constructor must not run")

    monkeypatch.setattr(httpx, "HTTPTransport", forbidden)
    with pytest.raises(HTTPException) as caught:
        meta_execution_transport(manifest(MetaConfigurationBundleV1.from_document(bundle_document())))
    assert caught.value.status_code == 409
