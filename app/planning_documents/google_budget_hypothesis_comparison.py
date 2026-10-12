"""Pure retained average-daily-setting comparison; no provider or runtime authority."""

from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from app.planning_documents.common import MAX_DOCUMENT_BYTES, Digest, NoAuthority
from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import VersionBinding
from app.planning_documents.google_budget_owner_contracts import (
    MAX_OWNER_WITNESS_BYTES,
    GoogleDailyBudgetOwnerWitnessV1,
    _instant,
    _originals,
)
from app.planning_documents.google_budget_owner_review_contracts import GoogleBudgetOwnerReviewV1

CONTRACT: Literal["inlet.google-daily-budget-hypothesis-comparison.v1"] = (
    "inlet.google-daily-budget-hypothesis-comparison.v1"
)
MAX_PACKET_BYTES = MAX_DOCUMENT_BYTES + MAX_OWNER_WITNESS_BYTES + 16_384


def _topology(witness: GoogleDailyBudgetOwnerWitnessV1) -> tuple[tuple[str, str, bool], ...]:
    # Full account/owner checked separately; include removed members without names or
    # snapshot-specific selection keys. ENABLED/PAUSED are eligible, not compared.
    return tuple(
        sorted(
            (
                target.canonical_entity_key,
                target.entity.reference.model_dump_json(),
                target.entity.status == "REMOVED",
            )
            for target in witness.catalog_evidence.catalog.targets
            if target.entity.kind == "campaign" and target.budget_owner_key == witness.owner_key
        )
    )


class GoogleBudgetHypothesisComparisonV1(NoAuthority):
    """Self-contained pure packet. Caller context cannot establish source authenticity."""

    schema_version: Literal["inlet.google-daily-budget-hypothesis-comparison.v1"] = CONTRACT
    document: PlanVersion
    binding: VersionBinding
    compared_at: AwareDatetime
    privacy_revision: int = Field(strict=True, ge=0)
    source_binding_digest: Digest
    integrity: Literal["clear", "invalidated"]
    fresh: GoogleDailyBudgetOwnerWitnessV1 | None
    application: Literal["unavailable"] = "unavailable"
    provider_edit_validity: Literal["not_assessed"] = "not_assessed"
    period_spending_compatibility: Literal["not_assessed"] = "not_assessed"
    causality: Literal["not_assessed"] = "not_assessed"

    @field_validator("compared_at", mode="before")
    @classmethod
    def original_instant(cls, value: Any) -> Any:
        return _instant(value)

    @model_validator(mode="before")
    @classmethod
    def strict_originals(cls, value: Any) -> Any:
        _originals(value)
        return value

    def _review(self) -> GoogleBudgetOwnerReviewV1:
        proof = self.document.google_budget_owner_review
        if proof is not None:
            for review in proof.reviews:
                if review.action_key == self.binding.action_key:
                    return review
        raise ValueError("exact retained owner review required")

    @model_validator(mode="after")
    def exact(self) -> "GoogleBudgetHypothesisComparisonV1":
        self.binding.assert_document(self.document)
        old = self._review().witness
        original = old.catalog_evidence.reference
        if (
            self.integrity != "clear"
            or self.compared_at < self.document.generated_at
            or self.privacy_revision != original.privacy_revision
            or self.source_binding_digest != original.source_binding_digest
        ):
            raise ValueError("invalidated comparison or original context mismatch")
        if self.fresh is not None:
            fresh = self.fresh
            source = fresh.catalog_evidence.reference
            if (
                source.account != original.account
                or source.privacy_revision != self.privacy_revision
                or source.source_binding_digest != self.source_binding_digest
                or fresh.owner_key != old.owner_key
                or fresh.currency != old.currency
                or fresh.catalog_evidence.catalog.native_observation.time_zone
                != old.catalog_evidence.catalog.native_observation.time_zone
                or fresh.reference_count != old.reference_count
                or _topology(fresh) != _topology(old)
                or not self.document.generated_at
                <= source.observation_started_at
                <= source.observed_at
                <= self.compared_at
                < source.expires_at
            ):
                raise ValueError("fresh owner identity, topology, source or interval mismatch")
        # Child serializers revalidate their own graphs. Avoid recursive self serialization.
        if (
            len(self.document.model_dump_json().encode())
            + (len(self.fresh.model_dump_json().encode()) if self.fresh else 0)
            + len(self.binding.model_dump_json().encode())
            > MAX_PACKET_BYTES - 4096
        ):
            raise ValueError("hypothesis comparison exceeds byte bound")
        return self

    @property
    def status(self) -> Literal["matches_hypothesis", "differs_from_hypothesis", "unavailable"]:
        checked = type(self).model_validate(self)
        if checked.fresh is None:
            return "unavailable"
        return (
            "matches_hypothesis"
            if checked.fresh.current_amount_micros
            == checked._review().intent.requested_amount_micros
            else "differs_from_hypothesis"
        )

    @property
    def unavailable_reason(self) -> str | None:
        checked = type(self).model_validate(self)
        return "No fresh retained owner observation supplied." if checked.fresh is None else None

    @model_serializer(mode="wrap")
    def checked_serialization(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        checked = type(self).model_validate(self)
        # Status is derived from retained bytes and the versioned interpretation.
        value: dict[str, Any] = handler(checked)
        return value
