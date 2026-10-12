"""Typed retained metadata is original evidence, never equivalence or authority."""

import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.campaign_performance.presence_contracts import AttributionBasisV1
from app.lifecycle.export_serializers import serialize
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanVersionRow
from app.planning_documents.selected_observation_provenance import (
    SelectedObservationProvenanceV1,
    selected_observation_provenance,
)
from app.planning_documents.selected_plan_contracts import SelectedPlanPinV1
from app.planning_documents.selected_plan_evidence import SelectedPlanCaptureV1
from app.planning_documents.selected_plan_history import validate_selected_historical_pin
from app.settings import Settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.capture_settings_reader_fixture import assert_prior_plan_reader
from tests.creative_q05_fixture import prepare_creative_q05_basis
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_reporting_comparability import review_browser
from tests.test_selected_plan_evidence import graph
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def legacy_pin_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    original = SelectedPlanCaptureV1._pin

    def legacy(value: SelectedPlanCaptureV1) -> SelectedPlanPinV1:
        pin = original(value)
        return SelectedPlanPinV1.model_validate(
            pin.model_copy(update={"observation_provenance": None})
        )

    monkeypatch.setattr(SelectedPlanCaptureV1, "_pin", legacy)


def test_exact_projection_and_absent_serializer_contract() -> None:
    source = graph()
    pin = source.pin()
    metadata = pin.observation_provenance
    assert metadata == selected_observation_provenance(source.capture)
    assert metadata is not None
    assert metadata.native_event_id == source.capture.request.selection.native_event_id
    assert metadata.attribution.click_window_days is None
    assert "confirmed_by_customer_id" not in metadata.model_dump_json()
    assert SelectedPlanPinV1.model_validate_json(pin.model_dump_json()) == pin
    assert pin.model_dump(include={"capture_id"}) == {"capture_id": pin.capture_id}
    assert "observation_provenance" not in pin.model_dump(exclude={"observation_provenance"})
    old = SelectedPlanPinV1.model_validate(pin.model_copy(update={"observation_provenance": None}))
    assert "observation_provenance" not in old.model_dump()
    assert old.model_dump(include={"observation_provenance"}) == {}
    assert "observation_provenance" not in json.loads(old.model_dump_json())
    assert pin.digest() != old.digest()
    known = metadata.model_copy(
        update={
            "attribution": AttributionBasisV1(
                click_window_days=7,
                view_window_days=0,
                report_time_basis="interaction",
                provenance="verified_request_contract",
                producer_contract=metadata.producer_contract,
            )
        }
    )
    assert SelectedObservationProvenanceV1.model_validate(known).attribution.view_window_days == 0
    with pytest.raises(ValueError):
        AttributionBasisV1.model_validate(
            known.attribution.model_copy(update={"provenance": "provider_default_unknown"})
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_event_owner_id", "9999999999"),
        ("native_event_id", "generic_total"),
        ("metric_family", "actions"),
        ("event_namespace", "meta_action_type"),
        ("producer_contract", "unrelated.v1"),
        ("requested_starts_on", "2026-09-28"),
        ("requested_ends_on", "2026-10-01"),
        ("completed_at", "2026-10-01T11:59:59Z"),
        ("capability", "comparable"),
    ],
)
def test_copied_malformed_provenance_cannot_enter_pin(field: str, value: Any) -> None:
    pin = graph().pin()
    assert pin.observation_provenance
    bad = pin.observation_provenance.model_copy(update={field: value})
    with pytest.raises(ValueError):
        SelectedPlanPinV1.model_validate(pin.model_copy(update={"observation_provenance": bad}))


def test_genuine_prechange_document_preserves_payload_digest_and_state() -> None:
    path = Path("tests/fixtures/selected_provenance/prechange-v5.json")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "81f40580521e03caa8eccc95188b25c2929a7608610283ccfd5b55b25a1186e3"
    )
    document = PlanVersion.model_validate_json(raw)
    assert document.digest() == "55e7570b06d6f25a86c3f8862f0281c73d1698a8b50d194b8ad58b1bac193280"
    assert document.model_dump(mode="json") == json.loads(raw)
    assert document.selected_reporting_proof
    from app.planning_documents.common import fingerprint

    original_accounts = json.loads(raw)["selected_reporting_proof"]["accounts"]
    for proof, original in zip(
        document.selected_reporting_proof.accounts, original_accounts, strict=True
    ):
        assert proof.state_digest() == fingerprint("inlet.local-reporting-state.v3", original)
        if proof.capture_pin:
            assert proof.capture_pin.observation_provenance is None


@pytest.mark.parametrize("legacy", [False, True])
def test_retained_metadata_actual_generate_history_export_and_replay(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    legacy: bool,
) -> None:
    fixture = prepare_creative_q05_basis(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path / "media",
    )
    basis = fixture.creative.basis
    alice, _, _ = replicas
    root = f"/api/customer/v1/workspaces/{basis.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=fixture.body)
    assert created.status_code == 201, created.text
    path = root + "/" + created.json()["plan_id"]
    intent = dict(expected_input_revision=1, expected_version=0, request_key="retained-metadata")
    with monkeypatch.context() as patch:
        if legacy:
            legacy_pin_projection(patch)
        generated = alice.post(path + "/generate", headers=headers(alice), json=intent)
    assert generated.status_code == 200, generated.text
    original = generated.json()
    document = PlanVersion.model_validate(original["document"])
    assert document.schema_version == (
        "inlet.plan-version.v1" if legacy else "inlet.plan-version.v3"
    )
    if not legacy:
        assert_prior_plan_reader(document, tmp_path)
    assert document.selected_reporting_proof
    pin = next(p.capture_pin for p in document.selected_reporting_proof.accounts if p.capture_pin)
    assert (pin.observation_provenance is None) is legacy
    with Session(customer_engine) as db:
        validate_selected_historical_pin(db, pin)
        if not legacy:
            assert pin.observation_provenance
            metadata = pin.observation_provenance
            assert metadata.attribution.provenance == "provider_default_unknown"
            assert metadata.schema_version == "inlet.selected-observation-provenance.v2"
            assert metadata.settings is not None
            assert metadata.settings.effective == metadata.attribution
            assert metadata.settings.requested.action_report_time is None
            for old_tag in ("inlet.plan-version.v1", "inlet.plan-version.v2"):
                with pytest.raises(ValueError, match="require plan-version.v3"):
                    PlanVersion.model_validate(
                        document.model_copy(update={"schema_version": old_tag})
                    )
            stripped = metadata.model_copy(
                update={"schema_version": "inlet.selected-observation-provenance.v1"}
            )
            with pytest.raises(ValueError, match="settings version mismatch"):
                SelectedPlanPinV1.model_validate(
                    pin.model_copy(update={"observation_provenance": stripped})
                )
            for field, value in (
                ("native_event_id", metadata.native_event_id + "9"),
                ("query_profile_digest", "f" * 64),
                ("completed_at", metadata.completed_at + timedelta(seconds=1)),
                ("capability", "unknown"),
                (
                    "attribution",
                    AttributionBasisV1(
                        click_window_days=7,
                        view_window_days=0,
                        report_time_basis="conversion",
                        provenance="observed_response",
                        producer_contract=metadata.producer_contract,
                    ),
                ),
            ):
                bad = metadata.model_copy(update={field: value})
                expected_error = {
                    "query_profile_digest": "settings request binding mismatch",
                    "attribution": "effective settings mismatch",
                }.get(field, "commitment mismatch")
                with pytest.raises(ValueError, match=expected_error):
                    validate_selected_historical_pin(
                        db, pin.model_copy(update={"observation_provenance": bad})
                    )
    calls = len(fixture.native_calls), len(fixture.creative.calls)
    read = alice.get(path)
    exported = alice.get(path + "/export?version=1")
    replay = alice.post(path + "/generate", headers=headers(alice), json=intent)
    assert read.status_code == exported.status_code == replay.status_code == 200
    assert (len(fixture.native_calls), len(fixture.creative.calls)) == calls
    assert read.json()["freshness"] == ("source_changed" if legacy else "current")
    assert read.json()["reasons"] == (["source_changed"] if legacy else [])
    artifacts = {
        "generated": original,
        "current": read.json(),
        "export": exported.json(),
        "replay": replay.json(),
    }
    for result in artifacts.values():
        assert result["document"] == original["document"]
        assert result["document_digest"] == document.digest()
    history = alice.get(path + "/versions/1")
    assert history.status_code == 200 and history.json()["document"] == original["document"]
    with Session(customer_engine) as db:
        stored = (
            db.execute(
                select(PlanVersionRow.__table__).where(
                    PlanVersionRow.workspace_id == basis.workspace_id,
                    PlanVersionRow.plan_id == document.inputs.plan_id,
                    PlanVersionRow.version == 1,
                )
            )
            .mappings()
            .one()
        )
        exported_row, excluded = serialize("planning_document_versions", dict(stored), db=db)
        assert not excluded and exported_row["document"] == original["document"]
    if legacy:
        next_intent = dict(expected_input_revision=1, expected_version=1, request_key="schema-v2")
        second = alice.post(path + "/generate", headers=headers(alice), json=next_intent)
        assert second.status_code == 200, second.text
        next_document = PlanVersion.model_validate(second.json()["document"])
        assert next_document.schema_version == "inlet.plan-version.v3"
        assert next_document.parent_digest == document.digest() and next_document.version == 2
        old_export = alice.get(path + "/export?version=1")
        old_replay = alice.post(path + "/generate", headers=headers(alice), json=intent)
        assert old_export.status_code == old_replay.status_code == 200
        assert (
            old_export.json()["document"] == old_replay.json()["document"] == original["document"]
        )
        (tmp_path / "mixed-schema-lineage.json").write_text(
            json.dumps(
                {
                    "v1": original,
                    "v2": second.json(),
                    "old_export": old_export.json(),
                    "old_replay": old_replay.json(),
                    "archive_v1": exported_row,
                },
                indent=2,
            )
        )
    assert not document.advertising_writes_enabled and document.spending_authority == "none"
    (tmp_path / "retained-metadata-artifacts.json").write_text(json.dumps(artifacts, indent=2))
    review_browser(
        tmp_path, {"retained_legacy" if legacy else "retained_typed": original["document"]}
    )
