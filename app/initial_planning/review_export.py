"""Protected hash provenance export; a nullable pointer never attests to current authority."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.initial_planning.contracts import Frozen
from app.publication.provider_contracts import Digest, Id
from app.shopify.security import utc


class ReviewLinkExport(Frozen):
    review_id: Id
    workspace_id: int = Field(strict=True, gt=0)
    preview_id: Id | None
    preview_workspace_id: int | None = Field(strict=True, gt=0)
    preview_account_id: int | None = Field(strict=True, gt=0)
    preview_campaign_id: int | None = Field(strict=True, gt=0)
    actor_id: Id
    environment: Literal["contract_test", "live"]
    preview_digest: Digest
    intent_digest: Digest
    policy_digest: Digest
    evidence_digest: Digest
    native_state_digest: Digest
    mandate_digest: Digest
    review_digest: Digest
    plan_digest: Digest
    expires_at: AwareDatetime
    created_at: AwareDatetime

    @model_validator(mode="after")
    def owned_pointer(self) -> "ReviewLinkExport":
        pointer = (
            self.preview_id,
            self.preview_workspace_id,
            self.preview_account_id,
            self.preview_campaign_id,
        )
        if any(value is None for value in pointer) != all(value is None for value in pointer):
            raise ValueError("incomplete retracted preview pointer")
        if self.preview_workspace_id not in {None, self.workspace_id}:
            raise ValueError("foreign preview pointer")
        if self.created_at >= self.expires_at:
            raise ValueError("invalid original provenance interval")
        return self


def export_review_link(row: Mapping[str, Any]) -> dict[str, Any]:
    # Explicit fields only. The internal original_session_digest is never read or
    # serialized; no arbitrary JSON or aggregate values exist in this projection.
    values = {key: row[key] for key in ReviewLinkExport.model_fields}
    for key in ("created_at", "expires_at"):
        if not isinstance(values[key], datetime):
            raise ValueError("invalid stored provenance time")
        values[key] = utc(values[key])
    return ReviewLinkExport.model_validate(values).model_dump(mode="json")
