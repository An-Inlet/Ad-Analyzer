"""Lossless resident snapshots; pure synthetic V6, never source authority."""

from datetime import datetime
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

import pytest
from app.planning_documents import version_row_admission as admission
from app.planning_documents.documents import PlanVersion

from tests.owner_review_v6_fixture import ready
from tests.test_owner_review_v6_pure import compose


@pytest.fixture
def document() -> PlanVersion:
    value = compose(ready())
    return PlanVersion.model_validate_json(value.model_dump_json())


@pytest.mark.parametrize("field", ["__pydantic_private__", "__pydantic_extra__"])
def test_empty_model_state_is_distinct_from_none(document: PlanVersion, field: str) -> None:
    original = admission._snapshot_version(document)
    assert original is not None
    copied = document.model_copy()
    object.__setattr__(copied, field, {})
    changed = admission._snapshot_version(copied)
    assert changed is not None and changed != original
    if field == "__pydantic_private__":
        assert copied != document
    else:
        # Installed Pydantic normalizes absent/empty extra state in equality.
        # The snapshot is deliberately stricter and selects ordinary fallback.
        assert copied == document


@pytest.mark.parametrize("fold", [0, 1])
def test_ambiguous_zoneinfo_is_ineligible(document: PlanVersion, fold: int) -> None:
    value = datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=fold)
    copied = document.model_copy(update={"generated_at": value})
    assert admission._snapshot_version(copied) is None


def test_current_unsafe_copy_changes_snapshot(document: PlanVersion) -> None:
    before = admission._snapshot_version(document)
    assert before is not None
    copied = document.model_copy(update={"version": True})
    assert admission._snapshot_version(copied) is None
    assert admission._snapshot_version(document) == before


def test_hostile_row_key_never_executes_equality() -> None:
    callbacks: list[str] = []

    class Hostile:
        def __hash__(self) -> int:
            return hash("workspace_id")

        def __eq__(self, other: object) -> bool:
            callbacks.append("equality")
            raise AssertionError("hostile row equality executed")

    row = {Hostile(): 1}
    assert admission._snapshot_row(cast(Any, row)) is None
    assert callbacks == []


@pytest.fixture
def row(document: PlanVersion) -> dict[str, object]:
    from app.planning_documents.storage import canonical

    return dict(
        workspace_id=document.inputs.workspace_id,
        plan_id=document.inputs.plan_id,
        version=document.version,
        input_revision=document.inputs.revision,
        parent_digest=document.parent_digest,
        generator_version=document.generator_version,
        policy_version=document.policy_version,
        actor_id=document.generated_by,
        generated_at=document.generated_at,
        valid_until=document.valid_until,
        privacy_revision=document.evidence[0].privacy_revision,
        canonical_json=canonical(document),
        digest=document.digest(),
    )


@pytest.mark.parametrize(
    "field",
    [
        "workspace_id",
        "plan_id",
        "version",
        "input_revision",
        "parent_digest",
        "generator_version",
        "policy_version",
        "actor_id",
        "generated_at",
        "valid_until",
        "privacy_revision",
        "canonical_json",
        "digest",
    ],
)
def test_each_row_commitment_changes_snapshot_and_original_decoder_refuses(
    row: dict[str, object], field: str
) -> None:
    from datetime import timedelta

    from app.planning_documents.storage import document_for_row

    # First prove this full row is an ordinary valid decoder input.
    original = document_for_row("planning_document_versions", row)
    before = admission._snapshot_row(row)
    assert before is not None
    changed = dict(row)
    value = changed[field]
    if type(value) is int:
        changed[field] = value + 1
    elif type(value) is datetime:
        changed[field] = value + timedelta(seconds=1)
    elif field == "canonical_json":
        changed[field] = "{}"
    elif field in {"digest", "parent_digest"}:
        changed[field] = "f" * 64
    else:
        changed[field] = str(value) + "-changed"
    assert admission._snapshot_row(changed) != before
    with pytest.raises(ValueError):
        document_for_row("planning_document_versions", changed)
    assert document_for_row("planning_document_versions", row) == original


def test_valid_offset_representation_falls_back_without_new_refusal(
    row: dict[str, object],
) -> None:
    from datetime import timedelta, timezone

    from app.planning_documents.storage import document_for_row

    original = document_for_row("planning_document_versions", row)
    changed = dict(row)
    value = changed["generated_at"]
    assert isinstance(value, datetime)
    changed["generated_at"] = value.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert admission._snapshot_row(changed) != admission._snapshot_row(row)
    assert document_for_row("planning_document_versions", changed) == original


def test_original_version_decoder_performs_five_root_validations(row: dict[str, object]) -> None:
    import sys
    from types import FrameType

    from app.planning_documents.storage import document_for_row
    from pydantic import BaseModel

    codes = {
        cast(Any, BaseModel.model_validate).__func__.__code__: "model",
        cast(Any, BaseModel.model_validate_json).__func__.__code__: "json",
    }
    calls: list[str] = []
    previous = sys.getprofile()

    def profile(
        frame: FrameType,
        event: Literal["call", "return", "c_call", "c_return", "c_exception"],
        arg: Any,
    ) -> None:
        if event == "call" and frame.f_locals.get("cls") is PlanVersion:
            label = codes.get(frame.f_code)
            if label is not None:
                calls.append(label)
        if previous is not None:
            previous(frame, event, arg)

    try:
        sys.setprofile(profile)
        document_for_row("planning_document_versions", row)
    finally:
        sys.setprofile(previous)
    assert calls.count("json") == 1
    assert calls.count("model") == 4
    assert len(calls) == 5
