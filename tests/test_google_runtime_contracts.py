from pathlib import Path
from typing import Any

import pytest
from app.production_runtime.configuration import (
    GoogleRuntimeConfigurationError,
    load_google_execution_manifest,
)
from app.production_runtime.contracts import (
    GoogleEvidenceDescriptor,
    GoogleExecutionManifestV1,
    RegisteredGoogleEvidenceSource,
    admit_source,
)
from pydantic import ValidationError


def manifest() -> GoogleExecutionManifestV1:
    return GoogleExecutionManifestV1(
        manifest_id="explicit_fixture",
        revision=1,
        environment="contract_test",
        api_version="v25",
        evidence_source_id="scenario_fixture",
        evidence_profile_digest="a" * 64,
        live_execution_enabled=False,
        activation_enabled=True,
        credential_minimum_remaining_seconds=300,
        context_lifetime_seconds=60,
    )


def test_no_source_or_live_scenario_never_constructs_reader() -> None:
    def forbidden(*args: Any) -> Any:
        raise AssertionError("source factory must not be invoked by admission")

    registered = RegisteredGoogleEvidenceSource(
        GoogleEvidenceDescriptor(
            source_id="scenario_fixture",
            profile_digest="a" * 64,
            environment="contract_test",
            kind="contract_scenario",
        ),
        forbidden,
    )
    value = manifest()
    assert admit_source(value, None) is None
    assert admit_source(value, registered) is registered
    live = GoogleExecutionManifestV1.model_validate(
        {**value.model_dump(), "environment": "live", "live_execution_enabled": True}
    )
    assert admit_source(live, registered) is None
    with pytest.raises(ValidationError):
        GoogleEvidenceDescriptor.model_validate(
            {**registered.descriptor.model_dump(), "environment": "live"}
        )


def test_manifest_loader_is_pinned_and_rejects_proof_payload(tmp_path: Path) -> None:
    value = manifest()
    path = tmp_path / "manifest.json"
    path.write_text(value.model_dump_json())
    assert load_google_execution_manifest(str(path), value.digest()) == value
    assert load_google_execution_manifest(None, None) is None
    with pytest.raises(GoogleRuntimeConfigurationError):
        load_google_execution_manifest(str(path), "b" * 64)
    with pytest.raises(ValidationError):
        GoogleExecutionManifestV1.model_validate(
            {**value.model_dump(), "portfolio_upper_micros": 0}
        )
    for field in (
        "context_lifetime_seconds",
        "credential_minimum_remaining_seconds",
        "activation_enabled",
    ):
        raw = value.model_dump()
        del raw[field]
        with pytest.raises(ValidationError):
            GoogleExecutionManifestV1.model_validate(raw)
