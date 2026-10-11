"""Standalone projected owner evidence; not authenticated discovery or economic proof."""

import copy
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from app.collectors.google_native_inventory import GoogleNativeInventory
from app.planning_catalog.metadata_contracts import PlanningMetadataV1
from app.planning_catalog.projection_v2 import project_v2
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.google_budget_intents import GoogleDailyBudgetIntentV1
from app.planning_documents.google_budget_owner_contracts import (
    GoogleBudgetOwnerUnavailable,
    GoogleDailyBudgetOwnerWitnessV1,
    derive_google_daily_budget_owner,
    owner_facts_digest,
    resolve_google_daily_budget_intent,
)
from pydantic import ValidationError

from tests.test_creative_composition import ready
from tests.test_planning_metadata_binding import bundle


def evidence(
    *, shift: int = 0, removed: bool = False, change: str | None = None
) -> CatalogEvidence:
    original, metadata = bundle("google")
    assert isinstance(original, GoogleNativeInventory)
    raw = original.model_dump(mode="python")
    campaign = raw["campaigns"][0]
    prefix = campaign["resource_name"].rsplit("/", 1)[0] + "/"
    budget = raw["campaign_budgets"][0]
    raw["campaigns"] = [
        dict(campaign, resource_name=prefix + ident, status=status)
        for ident, status in (("1", "ENABLED"), ("2", "PAUSED"))
    ]
    if removed:
        raw["campaigns"].append(dict(campaign, resource_name=prefix + "9", status="REMOVED"))
    budget.update(explicitly_shared=True, reference_count=2)
    if change == "amount":
        budget["amount_micros"] += 1
    elif change == "count":
        budget["reference_count"] = 3
    elif change == "period":
        budget["period"] = "CUSTOM_PERIOD"
    elif change == "status":
        raw["campaigns"][1]["status"] = "ENABLED"
    elif change == "unknown":
        raw["campaigns"][1]["status"] = "UNKNOWN"
    elif change == "member":
        raw["campaigns"][1]["resource_name"] = prefix + "3"
    raw["observed_at"] += timedelta(seconds=shift)
    raw["expires_at"] += timedelta(seconds=shift)
    raw["advertising_inventory_read_complete"] = change != "partial"
    inventory = GoogleNativeInventory.model_validate(raw)
    data = metadata.model_dump(mode="python")
    entity = next(e for e in data["entities"] if e["kind"] == "campaign")
    entities = []
    for c in inventory.campaigns:
        ident = c.resource_name.rsplit("/", 1)[1]
        row = copy.deepcopy(entity)
        row["reference"]["entity_id"] = ident
        row.update(name="Campaign " + ident, status=c.status)
        if change == "name" and ident == "2":
            row["name"] = "Renamed"
        if change == "contradiction" and ident == "2":
            row["status"] = "ENABLED"
        entities.append(row)
    data.update(
        entities=entities,
        native_inventory_digest=inventory.digest(),
        observed_at=inventory.observed_at,
        observation_started_at=inventory.observed_at,
        expires_at=inventory.expires_at,
    )
    for c in data["coverage"]:
        c["count"] = len(entities) if c["kind"] == "campaign" else 0
    metadata = PlanningMetadataV1.model_validate(data)
    catalog = project_v2(inventory, metadata)
    _, catalogs, _ = ready("google")
    ref = catalogs[0].reference.model_dump(mode="python")
    ref.update(
        document_digest=catalog.composite_digest,
        source_binding_digest=metadata.source_binding_digest,
        source_revision=metadata.connection_version,
        observation_started_at=min(
            catalog.native_observation.observation_started_at, metadata.observation_started_at
        ),
        observed_at=metadata.observed_at,
        expires_at=catalog.expires_at,
        reporting_window=dict(
            starts_at=metadata.reporting_starts_at, ends_at_exclusive=metadata.reporting_ends_at
        ),
    )
    return CatalogEvidence(reference=ref, catalog=catalog)


def derive(catalog: CatalogEvidence) -> GoogleDailyBudgetOwnerWitnessV1:
    owner = catalog.catalog.targets[0].budget_owner_key
    assert owner is not None
    return derive_google_daily_budget_owner(catalog, owner)


def intent(witness: GoogleDailyBudgetOwnerWitnessV1, **changes: Any) -> GoogleDailyBudgetIntentV1:
    values = dict(
        account_id=witness.representative.account.account_id,
        owner_selection_id="a" * 64,
        expected_observation_digest=witness.digest(),
        expected_owner_facts_digest=owner_facts_digest(witness),
        scenario_key="alternative",
        currency=witness.currency,
        cadence="daily",
        unit="micros",
        requested_amount_micros=witness.current_amount_micros,
    )
    values.update(changes)
    return GoogleDailyBudgetIntentV1.model_validate(values)


def test_derived_exact_owner_and_stable_facts_across_fresh_envelopes() -> None:
    first, later = derive(evidence()), derive(evidence(shift=10))
    assert first.digest() != later.digest()
    assert (
        first.catalog_evidence.catalog.composite_digest
        != later.catalog_evidence.catalog.composite_digest
    )
    assert first.affected_campaigns[0].selection_key != later.affected_campaigns[0].selection_key
    assert owner_facts_digest(first) == owner_facts_digest(later)
    assert first.representative == first.affected_campaigns[0]
    assert {t.provider_reference.entity_id for t in first.affected_campaigns} == {"1", "2"}
    assert first.reference_count == 2 and first.explicitly_shared is True
    assert (
        first.catalog_evidence.reference.coverage == "partial"
    )  # unrelated adgroup settings absent
    assert first.advertising_writes_enabled is False and first.spending_authority == "none"
    assert GoogleDailyBudgetOwnerWitnessV1.model_validate_json(first.model_dump_json()) == first
    assert derive(evidence()).model_dump_json() == first.model_dump_json()


@pytest.mark.parametrize("change", ["amount", "status", "name", "member"])
def test_changed_owned_facts_cannot_reuse_intent(change: str) -> None:
    original, changed = derive(evidence()), derive(evidence(change=change))
    assert owner_facts_digest(original) != owner_facts_digest(changed)
    supplied = intent(changed, expected_owner_facts_digest=owner_facts_digest(original))
    with pytest.raises(ValueError, match="exact owner"):
        resolve_google_daily_budget_intent(supplied, changed)


@pytest.mark.parametrize("change", ["count", "period", "partial", "unknown", "contradiction"])
def test_well_formed_ineligible_observations_have_typed_unavailability(change: str) -> None:
    with pytest.raises(GoogleBudgetOwnerUnavailable):
        derive(evidence(change=change))


def test_removed_rows_preserved_before_membership_filter() -> None:
    witness = derive(evidence(removed=True))
    assert len(witness.catalog_evidence.catalog.targets) == 3
    assert {t.provider_reference.entity_id for t in witness.affected_campaigns} == {"1", "2"}
    assert owner_facts_digest(witness) != owner_facts_digest(derive(evidence()))
    raw = witness.catalog_evidence.model_dump(mode="python")
    # A corrupted native/metadata commitment is malformed, never known absence.
    raw["catalog"]["metadata_observation"]["entities"][-1]["status"] = "PAUSED"
    with pytest.raises(ValueError):
        derive_google_daily_budget_owner(raw, witness.owner_key)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field,value",
    [
        ("explicitly_shared", 1),
        ("atomic_snapshot", 0),
        ("current_amount_micros", True),
        ("reference_count", "2"),
        ("owner_key", b"a" * 64),
    ],
)
def test_copied_witness_primitives_do_not_coerce(field: str, value: Any) -> None:
    witness = derive(evidence())
    with pytest.raises(ValueError):
        GoogleDailyBudgetOwnerWitnessV1.model_validate(witness.model_copy(update={field: value}))


@pytest.mark.parametrize("value", [True, 1770000000, 1770000000.0])
def test_copied_original_timestamps_reject_numeric_values(value: Any) -> None:
    catalog = evidence()
    copied = catalog.model_copy(
        update=dict(reference=catalog.reference.model_copy(update=dict(observed_at=value)))
    )
    with pytest.raises(ValueError):
        derive(copied)


def test_resolved_amount_currency_and_owner_bindings() -> None:
    witness = derive(evidence())
    for amount in (0, witness.current_amount_micros):
        resolved = resolve_google_daily_budget_intent(
            intent(witness, requested_amount_micros=amount), witness
        )
        assert resolved.owner_key == witness.owner_key
        assert resolved.observed_amount_micros == witness.current_amount_micros
    for changes in (
        dict(requested_amount_micros=witness.current_amount_micros + 1),
        dict(currency="EUR"),
        dict(account_id=999),
        dict(expected_observation_digest="0" * 64),
    ):
        with pytest.raises(ValueError):
            resolve_google_daily_budget_intent(intent(witness, **changes), witness)
    with pytest.raises(ValidationError):
        intent(witness, requested_amount_micros=True)


def test_missing_owner_and_corrupt_graph_are_distinct() -> None:
    with pytest.raises(GoogleBudgetOwnerUnavailable, match="missing"):
        derive_google_daily_budget_owner(evidence(), "0" * 64)
    catalog = evidence()
    broken = catalog.model_copy(
        update=dict(reference=catalog.reference.model_copy(update=dict(document_digest="0" * 64)))
    )
    with pytest.raises(ValueError):
        derive(broken)


@pytest.mark.parametrize(
    "module", ["google_budget_intents", "google_budget_owner_contracts", "documents"]
)
def test_fresh_imports_remain_cycle_free(module: str) -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                f"import app.planning_documents.{module}; "
                "import app.planning_documents.documents; "
                "import app.planning_documents.google_budget_owner_contracts"
            ),
        ],
        check=True,
        capture_output=True,
    )


def test_strict_utc_instant_fold_guard_and_equivalence() -> None:
    from app.planning_documents.google_budget_owner_contracts import _instant

    early = datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=0)
    late = early.replace(fold=1)
    assert early == late  # Python wall-time equality is not the accepted comparison.
    assert _instant(early) < _instant(late)
    assert _instant(early) == early.astimezone(UTC)


def retimed_catalog() -> CatalogEvidence:
    from app.planning_catalog.metadata_contracts import selection_key
    from app.publication.contracts import fingerprint as catalog_fingerprint

    data = evidence().model_dump(mode="python")
    zone = ZoneInfo("America/New_York")
    start = datetime(2026, 10, 30, tzinfo=zone)
    end = datetime(2026, 10, 31, tzinfo=zone)
    observed = datetime(2026, 11, 1, 0, 45, tzinfo=zone)
    expiry = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)
    composite = data["catalog"]
    for key in ("native_observation", "metadata_observation"):
        composite[key].update(
            reporting_starts_at=start,
            reporting_ends_at=end,
            observation_started_at=observed,
            observed_at=observed,
            expires_at=expiry,
        )
    metadata = PlanningMetadataV1.model_validate(composite["metadata_observation"])
    digest = catalog_fingerprint(
        "inlet.planning-catalog-composite.v1",
        dict(
            native_inventory_digest=composite["native_observation"]["inventory_digest"],
            metadata_digest=metadata.digest(),
        ),
    )
    composite.update(composite_digest=digest, expires_at=expiry)
    for target in composite["targets"]:
        target["selection_key"] = selection_key(
            target["canonical_entity_key"], metadata.source_binding_digest, digest
        )
    data["reference"].update(
        document_digest=digest,
        reporting_window=dict(starts_at=start, ends_at_exclusive=end),
        observation_started_at=observed,
        observed_at=observed,
        expires_at=expiry,
    )
    return CatalogEvidence.model_validate(data)


def test_fold_expiry_extension_cannot_hide_behind_datetime_equality() -> None:
    catalog = retimed_catalog()
    assert derive(catalog)
    later = catalog.reference.expires_at.replace(fold=1)
    assert later == catalog.reference.expires_at
    corrupted = catalog.model_copy(
        update=dict(reference=catalog.reference.model_copy(update=dict(expires_at=later)))
    )
    with pytest.raises(ValueError, match="envelope"):
        derive(corrupted)


def test_offset_equivalent_reference_and_cross_node_window_mismatch() -> None:
    catalog = retimed_catalog()
    equivalent = catalog.model_copy(
        update=dict(
            reference=catalog.reference.model_copy(
                update=dict(observed_at=catalog.reference.observed_at.astimezone(UTC))
            )
        )
    )
    assert derive(equivalent).current_amount_micros == derive(catalog).current_amount_micros
    window = catalog.reference.reporting_window
    assert window is not None
    bad_window = window.model_copy(
        update=dict(ends_at_exclusive=window.ends_at_exclusive + timedelta(hours=1))
    )
    corrupted = catalog.model_copy(
        update=dict(
            reference=catalog.reference.model_copy(update=dict(reporting_window=bad_window))
        )
    )
    with pytest.raises(ValueError):
        derive(corrupted)


def test_removed_member_setting_disagreement_is_not_filtered_away() -> None:
    catalog = evidence(removed=True)
    raw = catalog.model_dump(mode="python")
    # Native setting change itself does not alter the opaque inventory commitment.
    removed = next(
        t
        for t in raw["catalog"]["native_observation"]["targets"]
        if t["settings"]["status"] == "REMOVED"
    )
    removed["settings"]["budget_amount_micros"] += 1
    valid_projection = CatalogEvidence.model_validate(raw)
    with pytest.raises(GoogleBudgetOwnerUnavailable, match="disagree"):
        derive(valid_projection)


def test_witness_payload_bound_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.planning_documents import google_budget_owner_contracts

    monkeypatch.setattr(google_budget_owner_contracts, "MAX_OWNER_WITNESS_BYTES", 1)
    with pytest.raises(ValueError, match="byte bound"):
        derive(evidence())


def test_source_revision_cannot_escape_generation_binding() -> None:
    witness = derive(evidence())
    original = witness.catalog_evidence
    broken = original.model_copy(
        update=dict(
            reference=original.reference.model_copy(update=dict(source_revision="other-generation"))
        )
    )
    with pytest.raises(ValueError, match="source revision"):
        derive_google_daily_budget_owner(broken, witness.owner_key)
    copied = witness.model_copy(update=dict(catalog_evidence=broken))
    for validate in (
        GoogleDailyBudgetOwnerWitnessV1.model_validate,
        owner_facts_digest,
        lambda value: value.digest(),
    ):
        with pytest.raises(ValueError, match="source revision"):
            validate(copied)
