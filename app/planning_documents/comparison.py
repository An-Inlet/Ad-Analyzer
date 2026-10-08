"""Explain immutable successor changes; never transfer customer decisions."""

from typing import Literal

from pydantic import Field, JsonValue

from app.planning_documents.common import Digest, Frozen, NoAuthority, Positive
from app.planning_documents.documents import PlanVersion

MAX_CHANGES = 500


class VersionChange(Frozen):
    path: tuple[str, ...] = Field(min_length=1, max_length=30)
    before_present: bool
    after_present: bool
    before: JsonValue
    after: JsonValue


class VersionComparison(NoAuthority):
    schema_version: Literal["inlet.plan-version-comparison.v1"] = "inlet.plan-version-comparison.v1"
    previous_version: Positive
    current_version: Positive
    previous_digest: Digest
    current_digest: Digest
    changes: tuple[VersionChange, ...] = Field(max_length=MAX_CHANGES)
    omitted_changes: int = Field(strict=True, ge=0)
    decisions_carried_over: Literal[False] = False
    semantics: Literal["document_changes_not_causal_attribution"] = (
        "document_changes_not_causal_attribution"
    )


def comparable(document: PlanVersion) -> dict[str, JsonValue]:
    """Key collections by document identity; order-only changes are not content edits."""
    raw = document.model_dump(mode="json")
    for field in ("actions", "scenarios", "briefs", "evidence"):
        raw[field] = {item["key"]: item for item in raw[field]}
    raw["inputs"]["accounts"] = {
        str(item["account_id"]): item for item in raw["inputs"]["accounts"]
    }
    # Generated artifact stamps are shown separately by version headers. Evidence
    # timestamps, input revisions and actual generator/policy versions remain compared.
    for field in ("version", "parent_digest", "generated_at", "generated_by"):
        raw.pop(field)
    return raw


def compare_versions(previous: PlanVersion, current: PlanVersion) -> VersionComparison:
    previous = PlanVersion.model_validate(previous)
    current = PlanVersion.model_validate(current)
    if (
        previous.inputs.workspace_id != current.inputs.workspace_id
        or previous.inputs.plan_id != current.inputs.plan_id
        or current.version != previous.version + 1
        or current.parent_digest != previous.digest()
    ):
        raise ValueError("comparison requires exact owned direct predecessor")
    changes: list[VersionChange] = []
    total = 0

    def walk(
        path: tuple[str, ...],
        before: JsonValue,
        after: JsonValue,
        before_present: bool = True,
        after_present: bool = True,
    ) -> None:
        nonlocal total
        if before_present == after_present and before == after:
            return
        if (
            isinstance(before, dict)
            and isinstance(after, dict)
            and before_present
            and after_present
        ):
            for key in sorted(before.keys() | after.keys()):
                walk(path + (key,), before.get(key), after.get(key), key in before, key in after)
            return
        # New/deleted objects are a single structural change containing their fields;
        # positional lists (manual steps etc.) stay intact so meaning is not reordered.
        total += 1
        if len(changes) < MAX_CHANGES:
            changes.append(
                VersionChange(
                    path=path,
                    before_present=before_present,
                    after_present=after_present,
                    before=before,
                    after=after,
                )
            )

    walk((), comparable(previous), comparable(current))
    return VersionComparison(
        previous_version=previous.version,
        current_version=current.version,
        previous_digest=previous.digest(),
        current_digest=current.digest(),
        changes=tuple(changes),
        omitted_changes=total - len(changes),
    )
