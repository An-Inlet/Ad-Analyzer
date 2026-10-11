"""Standalone investigation proof; no generated-plan or execution capability."""

import json
from typing import Any, Literal

from pydantic import Field, SerializerFunctionWrapHandler, model_serializer, model_validator

from app.planning_documents.common import (
    MAX_DOCUMENT_BYTES,
    Digest,
    Key,
    NoAuthority,
    fingerprint,
    unique,
)
from app.planning_documents.google_budget_intents import (
    GoogleDailyBudgetIntentV1,
    ResolvedGoogleDailyBudgetIntentV1,
)
from app.planning_documents.google_budget_owner_contracts import (
    GoogleDailyBudgetOwnerWitnessV1,
    _originals,
    resolve_google_daily_budget_intent,
)


def owner_review_action_key(witness: GoogleDailyBudgetOwnerWitnessV1) -> str:
    witness = GoogleDailyBudgetOwnerWitnessV1.model_validate(witness)
    return "owner-review:" + fingerprint(
        "inlet.google-budget-owner-review-action.v1",
        dict(
            account=witness.representative.account.model_dump(mode="json"), owner=witness.owner_key
        ),
    )


class GoogleBudgetOwnerReviewV1(NoAuthority):
    schema_version: Literal["inlet.google-budget-owner-review.v1"] = (
        "inlet.google-budget-owner-review.v1"
    )
    action_key: Key
    intent: ResolvedGoogleDailyBudgetIntentV1
    witness: GoogleDailyBudgetOwnerWitnessV1
    disposition: Literal["investigate_only"] = "investigate_only"
    period_spending_compatibility: Literal["not_assessed"] = "not_assessed"
    provider_edit_validity: Literal["not_assessed"] = "not_assessed"
    application: Literal["unavailable"] = "unavailable"

    @model_serializer(mode="wrap")
    def checked_serialization(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        checked = type(self).model_validate(self)
        value: dict[str, Any] = handler(checked)
        return value

    @model_validator(mode="before")
    @classmethod
    def original_values(cls, value: Any) -> Any:
        _originals(value)
        return value

    @model_validator(mode="after")
    def exact(self) -> "GoogleBudgetOwnerReviewV1":
        request = GoogleDailyBudgetIntentV1.model_validate(
            {k: getattr(self.intent, k) for k in GoogleDailyBudgetIntentV1.model_fields}
        )
        resolved = resolve_google_daily_budget_intent(request, self.witness)
        if resolved.model_dump_json() != self.intent.model_dump_json():
            raise ValueError("review intent differs from exact owner witness")
        if self.action_key != owner_review_action_key(self.witness):
            raise ValueError("exact owner review action key required")
        return self


class GoogleBudgetOwnerReviewProofV1(NoAuthority):
    schema_version: Literal["inlet.google-budget-owner-review-proof.v1"] = (
        "inlet.google-budget-owner-review-proof.v1"
    )
    input_digest: Digest
    reviews: tuple[GoogleBudgetOwnerReviewV1, ...] = Field(max_length=20)

    @model_serializer(mode="wrap")
    def checked_serialization(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        checked = type(self).model_validate(self)
        value: dict[str, Any] = handler(checked)
        return value

    @model_validator(mode="before")
    @classmethod
    def original_values(cls, value: Any) -> Any:
        _originals(value)
        return value

    @model_validator(mode="after")
    def complete(self) -> "GoogleBudgetOwnerReviewProofV1":
        unique(tuple(r.action_key for r in self.reviews), "owner review action")
        unique(
            tuple(
                (r.witness.representative.account.model_dump_json(), r.witness.owner_key)
                for r in self.reviews
            ),
            "full account owner review",
        )
        catalogs: dict[str, str] = {}
        for review in self.reviews:
            catalog = review.witness.catalog_evidence
            key = review.witness.representative.account.model_dump_json()
            value = catalog.model_dump_json()
            if catalogs.setdefault(key, value) != value:
                raise ValueError("repeated account catalogs must match exactly")
        # Avoid invoking this proof's wrap serializer from its own validator.
        # Child serialization is independently checked and cannot recurse to the parent.
        payload = dict(
            schema_version=self.schema_version,
            advertising_writes_enabled=self.advertising_writes_enabled,
            spending_authority=self.spending_authority,
            input_digest=self.input_digest,
            reviews=[r.model_dump(mode="json") for r in self.reviews],
        )
        if (
            len(
                json.dumps(
                    payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
                ).encode()
            )
            > MAX_DOCUMENT_BYTES
        ):
            raise ValueError("owner review proof exceeds document byte bound")
        return self
