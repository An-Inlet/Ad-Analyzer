"""Standalone retained empty-query proof; no actual ownership or runtime claim."""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from app.collectors.meta_native_inventory import MetaNativeInventory
from app.planning_catalog.metadata_contracts import PlanningMetadataV1
from app.planning_catalog.projection_v2 import project_v2
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.context import AccountTarget
from app.planning_documents.creative_production_contracts import CreativeProposalV1
from app.planning_documents.documents import PlanVersion
from app.planning_documents.empty_catalog_contracts import EmptyDeclaredCatalogWitnessV1
from app.planning_documents.ports import CatalogEvidence as PublicCatalogEvidence
from pydantic import ValidationError

from tests.test_creative_composition import compose, ready
from tests.test_creative_plan_document import document_values
from tests.test_planning_metadata_binding import bundle


def empty_evidence() -> CatalogEvidence:
    original, metadata = bundle("meta")
    raw = original.model_dump(mode="python")
    raw.update(campaigns=(), adsets=())
    inventory = MetaNativeInventory.model_validate(raw)
    data = metadata.model_dump(mode="python")
    data.update(entities=(), native_inventory_digest=inventory.digest())
    for item in data["coverage"]:
        item["count"] = 0
    catalog = project_v2(inventory, PlanningMetadataV1.model_validate(data))
    _, references, _ = ready()
    ref = references[0].reference.model_dump(mode="python")
    ref.update(
        account=dict(
            workspace_id=metadata.workspace_id,
            account_id=metadata.account_id,
            connection_id=metadata.connection_id,
            platform=metadata.platform,
            connection_version=metadata.connection_version,
        ),
        workspace_id=metadata.workspace_id,
        document_digest=catalog.composite_digest,
        source_binding_digest=metadata.source_binding_digest,
        observation_started_at=metadata.observation_started_at,
        observed_at=metadata.observed_at,
        expires_at=catalog.expires_at,
        coverage="partial",
        reporting_window=dict(
            starts_at=metadata.reporting_starts_at, ends_at_exclusive=metadata.reporting_ends_at
        ),
    )
    return CatalogEvidence(reference=ref, catalog=catalog)


def witness() -> EmptyDeclaredCatalogWitnessV1:
    evidence = empty_evidence()
    assert evidence.reference.account is not None
    return EmptyDeclaredCatalogWitnessV1(
        catalog_evidence=evidence,
        prerequisite_action_key=f"review:account_{evidence.reference.account.account_id}",
    )


def proposal() -> CreativeProposalV1:
    inputs, catalogs, basis = ready()
    original = compose(inputs, catalogs, basis).proposals[0]
    proof = witness()
    account = proof.catalog_evidence.reference.account
    assert account is not None
    target = AccountTarget(account=account)
    action = original.action.model_copy(
        update=dict(
            target=target,
            key=f"creative:account_{account.account_id}",
            prerequisites=(proof.prerequisite_action_key,),
            evidence_keys=(
                proof.catalog_evidence.reference.key,
                original.production.basis_evidence_key,
                *original.brief.claim_evidence_keys,
            ),
        )
    )
    brief = original.brief.model_copy(
        update=dict(
            target=target,
            key=f"brief:account_{account.account_id}",
            action_key=action.key,
        )
    )
    return CreativeProposalV1(
        action=action,
        brief=brief,
        production=original.production,
        target_basis="observed_empty_account",
        empty_catalog_witness=proof,
    )


def test_shared_class_and_exact_legacy_nested_bytes() -> None:
    assert PublicCatalogEvidence is CatalogEvidence
    expected = json.loads(
        (Path(__file__).parent / "fixtures/q08_empty_proof/legacy-goldens.json").read_text()
    )

    def digest(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    for platform in ("meta", "tiktok"):
        inputs, catalogs, basis = ready(platform)
        for name, value in (
            ("catalog", catalogs[0]),
            ("composition", compose(inputs, catalogs, basis)),
            ("document", PlanVersion(**document_values(platform))),
        ):
            golden = expected[platform + "_" + name]
            assert digest(value.model_dump_json()) == golden["json"]
            assert digest(repr(value.model_dump(mode="python"))) == golden["python"]
            assert value.digest() == golden["digest"]
    assert (
        digest(json.dumps(CatalogEvidence.model_json_schema(), sort_keys=True))
        == expected["catalog_schema"]
    )


@pytest.mark.parametrize(
    "first", ["ports", "catalog_evidence", "creative_production_contracts", "documents"]
)
def test_fresh_imports(first: str) -> None:
    code = (
        f"import app.planning_documents.{first}; "
        "from app.planning_documents.ports import CatalogEvidence as A; "
        "from app.planning_documents.catalog_evidence import CatalogEvidence as B; assert A is B"
    )
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)


def test_empty_witness_and_account_proposal_roundtrip() -> None:
    value = witness()
    assert EmptyDeclaredCatalogWitnessV1.model_validate_json(value.model_dump_json()) == value
    p = proposal()
    assert CreativeProposalV1.model_validate_json(p.model_dump_json()) == p
    assert p.model_dump()["target_basis"] == "observed_empty_account"
    assert p.model_dump()["empty_catalog_witness"]
    assert len(value.model_dump_json().encode()) < 262_144


@pytest.mark.parametrize(
    "field,value",
    [
        ("prerequisite_action_key", "review:account_999"),
        ("catalog_evidence", None),
    ],
)
def test_unsafe_copy_digest_revalidates(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        witness().model_copy(update={field: value}).digest()


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "campaign_basis",
        "wrong_account",
        "missing_prerequisite",
        "missing_catalog_ref",
        "no_image",
    ],
)
def test_account_proposal_requires_complete_local_bindings(change: str) -> None:
    p = proposal()
    raw = p.model_dump(mode="python")
    if change == "missing":
        raw["empty_catalog_witness"] = None
    elif change == "campaign_basis":
        raw["target_basis"] = "existing_campaign"
    elif change == "wrong_account":
        raw["action"]["target"]["account"]["connection_version"] = "different"
        raw["brief"]["target"] = raw["action"]["target"]
    elif change == "missing_prerequisite":
        raw["action"]["prerequisites"] = ()
    elif change == "missing_catalog_ref":
        raw["action"]["evidence_keys"] = (p.production.basis_evidence_key,)
    else:
        raw["production"].update(
            source_images=(), selected_image_id=None, source_image_status="not_supplied"
        )
    with pytest.raises(ValidationError):
        CreativeProposalV1.model_validate(raw)


@pytest.mark.parametrize(
    "change",
    [
        "nonempty",
        "scope",
        "reason",
        "count",
        "privacy_type",
        "numeric_time",
        "naive_time",
        "boolean_flag",
        "digest",
    ],
)
def test_witness_tampering_refused(change: str) -> None:
    raw = witness().model_dump(mode="python")
    e = raw["catalog_evidence"]
    n = e["catalog"]["native_observation"]
    if change == "nonempty":
        _, catalogs, _ = ready()
        raw["catalog_evidence"] = catalogs[0]
    elif change == "scope":
        n["coverage"][0]["scope"] = "provider_campaigns"
    elif change == "reason":
        n["coverage"][0]["reasons"] = ("unknown_scope",)
    elif change == "count":
        n["coverage"][0]["observed_count"] = 1
    elif change == "privacy_type":
        e["reference"]["privacy_revision"] = True
    elif change == "numeric_time":
        e["reference"]["observed_at"] = 1234567890
    elif change == "naive_time":
        e["reference"]["observed_at"] = datetime(2026, 10, 1)
    elif change == "boolean_flag":
        n["advertising_writes_enabled"] = 0
    else:
        e["catalog"]["composite_digest"] = "0" * 64
    with pytest.raises(ValidationError):
        EmptyDeclaredCatalogWitnessV1.model_validate(raw)


def test_size_bound_fails_without_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.planning_documents import empty_catalog_contracts

    raw = witness().model_dump()
    monkeypatch.setattr(empty_catalog_contracts, "MAX_EMPTY_CATALOG_BYTES", 1)
    with pytest.raises(ValidationError, match="exceeds document bound"):
        EmptyDeclaredCatalogWitnessV1.model_validate(raw)


def test_strict_instant_fold_and_offset_equivalence() -> None:
    from app.planning_documents.empty_catalog_contracts import _instant

    zone = ZoneInfo("America/New_York")
    early = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)
    late = early.replace(fold=1)
    assert _instant(early) < _instant(late)
    assert _instant(late) == late.astimezone(UTC)
    assert _instant(early.isoformat()) == _instant(early)
    assert _instant(late) - _instant(early) == timedelta(hours=1)


def _rehash(raw: dict[str, Any]) -> None:
    from app.publication.contracts import fingerprint

    evidence = raw["catalog_evidence"]
    catalog = evidence["catalog"]
    metadata = PlanningMetadataV1.model_validate(catalog["metadata_observation"])
    catalog["composite_digest"] = fingerprint(
        "inlet.planning-catalog-composite.v1",
        dict(
            native_inventory_digest=catalog["native_observation"]["inventory_digest"],
            metadata_digest=metadata.digest(),
        ),
    )
    evidence["reference"]["document_digest"] = catalog["composite_digest"]


def test_actual_witness_rejects_fold_reversed_interval_after_valid_rehash() -> None:
    raw = witness().model_dump(mode="python")
    zone = ZoneInfo("America/New_York")
    start = datetime(2026, 11, 1, 1, 15, tzinfo=zone, fold=1)
    observed = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)
    end = datetime(2026, 11, 1, 2, tzinfo=zone)
    period_start = datetime(2026, 10, 1, tzinfo=zone)
    period_end = datetime(2026, 11, 1, tzinfo=zone)
    e = raw["catalog_evidence"]
    for value in (e["catalog"]["native_observation"], e["catalog"]["metadata_observation"]):
        value.update(
            reporting_starts_at=period_start,
            reporting_ends_at=period_end,
            observation_started_at=start,
            observed_at=observed,
            expires_at=end,
        )
    e["catalog"]["expires_at"] = end
    e["reference"].update(
        observation_started_at=start,
        observed_at=observed,
        expires_at=end,
        reporting_window=dict(starts_at=period_start, ends_at_exclusive=period_end),
    )
    _rehash(raw)
    with pytest.raises(ValidationError, match="instants reversed"):
        EmptyDeclaredCatalogWitnessV1.model_validate(raw)


def test_offset_equivalent_originals_preserved_after_rehash() -> None:
    from datetime import timezone

    raw = witness().model_dump(mode="python")
    zone = timezone(timedelta(hours=5, minutes=30))

    def change(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.astimezone(zone)
        if isinstance(value, dict):
            return {key: change(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return tuple(change(item) for item in value)
        return value

    raw = change(raw)
    _rehash(raw)
    parsed = EmptyDeclaredCatalogWitnessV1.model_validate(raw)
    assert parsed.catalog_evidence.reference.observed_at.utcoffset() == timedelta(
        hours=5, minutes=30
    )
    assert EmptyDeclaredCatalogWitnessV1.model_validate_json(parsed.model_dump_json()) == parsed


@pytest.mark.parametrize("changed_node", ["reference", "native"])
def test_whole_witness_rejects_cross_node_reporting_fold(changed_node: str) -> None:
    raw = witness().model_dump(mode="python")
    zone = ZoneInfo("America/New_York")
    start = datetime(2026, 10, 1, tzinfo=zone)
    end = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)
    observed = datetime(2026, 11, 1, 3, tzinfo=zone)
    expiry = observed + timedelta(minutes=5)
    e = raw["catalog_evidence"]
    for value in (e["catalog"]["native_observation"], e["catalog"]["metadata_observation"]):
        value.update(
            reporting_starts_at=start,
            reporting_ends_at=end,
            observation_started_at=observed,
            observed_at=observed,
            expires_at=expiry,
        )
    e["catalog"]["expires_at"] = expiry
    e["reference"].update(
        observation_started_at=observed,
        observed_at=observed,
        expires_at=expiry,
        reporting_window=dict(starts_at=start, ends_at_exclusive=end),
    )
    if changed_node == "reference":
        e["reference"]["reporting_window"]["ends_at_exclusive"] = end.replace(fold=1)
    else:
        e["catalog"]["native_observation"]["reporting_ends_at"] = end.replace(fold=1)
    _rehash(raw)
    # Legacy comparisons alone admit this equal-wall-clock graph. The new proof
    # must additionally compare exact UTC instants without rewriting old models.
    CatalogEvidence.model_validate(e)
    with pytest.raises(ValidationError, match="reporting window instant mismatch"):
        EmptyDeclaredCatalogWitnessV1.model_validate(raw)
