"""Synthetic normalized facts qualify mechanics, never native extraction or authority."""

from copy import deepcopy
from datetime import datetime
from typing import Any

import pytest
from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import ManualAssertion, ReadObservedStatus
from app.planning_documents.field_comparison import (
    ComparisonAdmissionV1,
    FieldFactsV1,
    FieldSnapshotV1,
    compare_fields,
)
from app.planning_documents.storage import canonical, document_for_row, export_row

from tests.test_planning_document_contracts import packet

AT = datetime.fromisoformat("2026-10-01T01:20:00+00:00")
VALUES: tuple[dict[str, Any], ...] = (
    {"field": "delivery_status", "value": "paused"},
    {"field": "landing_page", "value": "https://example.invalid/offer"},
    {"field": "country_targets", "value": ["US", "CA"]},
)


def document(field: str = "delivery_status") -> PlanVersion:
    data = packet()
    data["actions"][0].update(
        kind={
            "delivery_status": "status_review",
            "landing_page": "landing_page_review",
            "country_targets": "targeting_review",
        }[field],
        proposed_fields=[
            dict(
                key=f"field_{i}",
                availability="supported",
                current=value,
                proposed=value,
                evidence_key="catalog",
                verification_criterion="Compare exact value",
            )
            for i, value in enumerate(VALUES)
            if value["field"] == field
        ],
    )
    return PlanVersion.model_validate(data)


def admission(doc: PlanVersion) -> ComparisonAdmissionV1:
    return ComparisonAdmissionV1.model_validate(
        dict(
            binding=dict(
                workspace_id=1,
                plan_id=doc.inputs.plan_id,
                version=doc.version,
                document_digest=doc.digest(),
                action_key=doc.actions[0].key,
                action_digest=doc.actions[0].digest(),
            ),
            event_id="e" * 32,
            compared_at=AT,
            privacy_revision=0,
            source_binding_digest="d" * 64,
            extraction_contract="synthetic.fixture.fields.v1",
        )
    )


def snapshot_data(doc: PlanVersion, values: Any = VALUES) -> dict[str, Any]:
    target = doc.actions[0].target.model_dump(mode="json")
    # Names and selection keys may legitimately change after generation.
    target.update(display_name="Renamed", selection_key="f" * 64, catalog_evidence_key="fresh")
    facts = FieldFactsV1.model_validate(
        dict(
            target=target,
            extraction_contract="synthetic.fixture.fields.v1",
            observation_started_at="2026-10-01T01:15:00Z",
            observed_at="2026-10-01T01:16:00Z",
            expires_at="2026-10-01T02:00:00Z",
            values=values,
        )
    )
    source = doc.evidence[0].model_dump(mode="json")
    source.update(
        key="fresh",
        document_schema=facts.schema_version,
        document_digest=facts.digest(),
        observation_started_at=facts.observation_started_at,
        observed_at=facts.observed_at,
        expires_at=facts.expires_at,
    )
    return dict(facts=facts.model_dump(mode="python"), evidence=dict(source=source, target=target))


@pytest.mark.parametrize(
    "variant,expected",
    [
        ("all", "matching"),
        ("other_field", "unavailable"),
        ("conflict", "conflicting"),
        ("empty", "unavailable"),
        ("none", "unavailable"),
    ],
)
def test_status_precedence_and_exact_coverage(variant: str, expected: str) -> None:
    doc = document()
    values = deepcopy(list(VALUES))
    if variant == "other_field":
        values = values[1:]
    if variant.startswith("conflict"):
        values[0]["value"] = "enabled"
    if variant == "empty":
        values = []
    snapshot = (
        None if variant == "none" else FieldSnapshotV1.model_validate(snapshot_data(doc, values))
    )
    result = compare_fields(doc, admission(doc), snapshot)
    assert result.status == expected and len(result.comparisons) == 1
    assert result.applied_by is None and result.causality == "not_assessed"
    assert result.spending_authority == "none" and result.advertising_writes_enabled is False
    assert all(
        c.evidence is None and c.unavailable_reason
        for c in result.comparisons
        if c.observed is None
    )
    assert ReadObservedStatus.model_validate_json(result.model_dump_json()) == result
    assert any("not verify implementation" in limitation for limitation in result.limitations)


@pytest.mark.parametrize(
    "fault",
    [
        "digest",
        "schema",
        "value_bytes",
        "interval_bytes",
        "target_bytes",
        "privacy",
        "source",
        "contract",
        "account",
        "connection_generation",
        "native_id",
        "owner",
        "canonical",
        "expired",
        "future",
        "before_plan",
        "duplicate_field",
        "duplicate_country",
    ],
)
def test_forged_stale_foreign_or_ambiguous_snapshot_refused(fault: str) -> None:
    doc = document()
    raw = snapshot_data(doc)
    context = admission(doc)
    if fault == "digest":
        raw["evidence"]["source"]["document_digest"] = "0" * 64
    elif fault == "schema":
        raw["evidence"]["source"]["document_schema"] = "unqualified"
    elif fault == "value_bytes":
        raw["facts"]["values"][0]["value"] = "enabled"
    elif fault == "interval_bytes":
        raw["facts"]["observed_at"] = AT
    elif fault == "target_bytes":
        raw["facts"]["target"]["display_name"] = "Other"
    elif fault in {"privacy", "source", "contract", "expired", "future", "before_plan"}:
        fields = {
            "privacy": ("privacy_revision", 1),
            "source": ("source_binding_digest", "0" * 64),
            "contract": ("extraction_contract", "other"),
            "expired": ("compared_at", "2026-10-01T02:00:00Z"),
            "future": ("compared_at", "2026-10-01T01:15:30Z"),
            "before_plan": ("compared_at", "2026-10-01T00:00:00Z"),
        }
        field, value = fields[fault]
        context = context.model_copy(update={field: value})
    elif fault in {"account", "connection_generation", "native_id", "owner", "canonical"}:
        target = raw["facts"]["target"]
        if fault == "account":
            target["account"]["account_id"] = 2
        elif fault == "connection_generation":
            target["account"]["connection_version"] = "v2"
        elif fault == "native_id":
            target["provider_reference"]["entity_id"] = "999"
        elif fault == "owner":
            target["budget_owner_key"] = "1" * 64
        else:
            target["canonical_entity_key"] = "2" * 64
        raw["evidence"]["target"] = deepcopy(target)
        raw["evidence"]["source"]["account"] = deepcopy(target["account"])
        raw["evidence"]["source"]["document_digest"] = FieldFactsV1.model_validate(
            raw["facts"]
        ).digest()
    elif fault == "duplicate_field":
        raw["facts"]["values"] = (VALUES[0], VALUES[0])
    else:
        raw["facts"]["values"] = ({"field": "country_targets", "value": ["US", "US"]},)
    with pytest.raises(ValueError):
        compare_fields(doc, context, FieldSnapshotV1.model_validate(raw))


@pytest.mark.parametrize(
    "value",
    [
        {"field": "country_targets", "value": ["CA", "US"]},
        {"field": "landing_page", "value": "https://example.invalid/offer/"},
    ],
)
def test_no_implicit_url_or_country_normalization(value: dict[str, Any]) -> None:
    doc = document(value["field"])
    result = compare_fields(
        doc, admission(doc), FieldSnapshotV1.model_validate(snapshot_data(doc, [value]))
    )
    assert result.status == "conflicting"


def test_unsupported_only_action_is_unavailable_without_fabricated_target() -> None:
    raw = packet()
    raw["actions"][0]["kind"] = "status_review"
    raw["actions"][0]["proposed_fields"] = [
        dict(
            key="budget",
            availability="unavailable",
            field="delivery_status",
            reason="Native status semantics unavailable",
        )
    ]
    doc = PlanVersion.model_validate(raw)
    result = compare_fields(doc, admission(doc), None)
    assert result.status == "unavailable" and result.comparisons == ()
    assert any("Unsupported proposed fields" in text for text in result.limitations)


@pytest.mark.parametrize(
    "fault", ["workspace", "plan", "version", "document", "action", "unsafe_snapshot"]
)
def test_binding_and_unsafe_instances_are_revalidated(fault: str) -> None:
    doc = document()
    context = admission(doc)
    snap = FieldSnapshotV1.model_validate(snapshot_data(doc))
    if fault == "unsafe_snapshot":
        snap = snap.model_copy(
            update={"facts": snap.facts.model_copy(update={"values": ("forged",)})}
        )
    else:
        field, value = {
            "workspace": ("workspace_id", 2),
            "plan": ("plan_id", "f" * 32),
            "version": ("version", 2),
            "document": ("document_digest", "0" * 64),
            "action": ("action_digest", "0" * 64),
        }[fault]
        context = context.model_copy(
            update={"binding": context.binding.model_copy(update={field: value})}
        )
    with pytest.raises(ValueError):
        compare_fields(doc, context, snap)


def test_report_retraction_and_reserved_export_remain_separate() -> None:
    doc = document()
    context = admission(doc)
    original = canonical(doc)
    result = compare_fields(doc, context, FieldSnapshotV1.model_validate(snapshot_data(doc)))
    report = ManualAssertion(
        **context.binding.model_dump(),
        event_id="a" * 32,
        actor_id="b" * 32,
        recorded_at=AT,
        assertion="customer_reports_applied",
        reported_applied_at=AT,
        supersedes_event_id=None,
        statement="Customer statement",
    )
    retraction = ManualAssertion(
        **context.binding.model_dump(),
        event_id="c" * 32,
        actor_id="b" * 32,
        recorded_at=AT,
        assertion="retracted",
        reported_applied_at=None,
        supersedes_event_id=report.event_id,
        statement="Customer correction",
    )
    for record in (report, retraction):
        record.assert_document(doc)
    assert (
        result.status == "matching"
        and report.verification == retraction.verification == "customer_report_only"
    )
    row = dict(
        workspace_id=1,
        plan_id=doc.inputs.plan_id,
        sequence=3,
        event_id=result.event_id,
        version=1,
        action_key=result.action_key,
        action_digest=result.action_digest,
        kind="observation",
        actor_id="b" * 32,
        recorded_at=result.observed_at,
        prior_sequence=None,
        canonical_json=canonical(result),
        digest=result.digest(),
    )
    assert document_for_row("planning_document_events", row) == result
    exported = export_row("planning_document_events", row)
    assert exported["document"] == result.model_dump(mode="json")
    assert (
        "actor_id" not in exported["document"] and "reported_applied_at" not in exported["document"]
    )
    assert canonical(doc) == original
    assert canonical(result) == canonical(
        compare_fields(doc, context, FieldSnapshotV1.model_validate(snapshot_data(doc)))
    )
    row["workspace_id"] = 2
    with pytest.raises(ValueError):
        document_for_row("planning_document_events", row)


def test_account_level_investigation_requires_no_native_snapshot() -> None:
    raw = packet()
    raw["actions"][0]["target"] = {"account": raw["inputs"]["accounts"][0], "scope": "account"}
    doc = PlanVersion.model_validate(raw)
    result = compare_fields(doc, admission(doc), None)
    assert result.status == "unavailable" and result.comparisons == ()


def test_current_action_schema_does_not_invent_multifield_partial_support() -> None:
    raw = document().model_dump(mode="json")
    extra = deepcopy(raw["actions"][0]["proposed_fields"][0])
    extra.update(key="url", current=VALUES[1], proposed=VALUES[1])
    raw["actions"][0]["proposed_fields"].append(extra)
    with pytest.raises(ValueError, match="incompatible with action kind"):
        PlanVersion.model_validate(raw)
