"""Pure strict preview/intent/row binding; no claim of currentness or authority."""

from collections.abc import Mapping
from typing import Any

from app.initial_planning.contracts import InitialPreviewV1, PreviewIntentV1
from app.initial_planning.native_budget_contracts import native_budget_choice_digest
from app.initial_planning.preview_v2 import InitialPreviewV2, PreviewIntentV2, parse_initial_preview
from app.shopify.security import utc


def bind_preview_row(row: Mapping[str, Any]) -> InitialPreviewV1 | InitialPreviewV2:
    document = parse_initial_preview(row["document"])
    intent: PreviewIntentV1 | PreviewIntentV2
    if isinstance(document, InitialPreviewV1):
        intent = PreviewIntentV1.model_validate(row["intent"])
        if row["native_state_digest"] != document.native_state_digest:
            raise ValueError("initial native state binding mismatch")
    else:
        intent = PreviewIntentV2.model_validate(row["intent"])
        if (
            row["native_state_digest"] is not None
            or intent.environment != document.environment
            or intent.profile_digest != document.profile_digest
            or intent.goal_digest != row["goal_digest"]
        ):
            raise ValueError("initial native observation binding mismatch")
        native = document.native_observation
        if native is not None and (
            intent.native_option_id != native_budget_choice_digest(native)
            or native.request.goal_digest != row["goal_digest"]
            or native.request.scope.connection_version.split(":")[-1]
            != str(row["source_generation"])
            or row["mandate_digest"] is None
        ):
            raise ValueError("initial native selection binding mismatch")
        if native is None and row["mandate_digest"] is not None:
            raise ValueError("initial absent native selection has mandate commitment")
    cohort = document.objective.cohort
    if (
        document.digest() != row["document_digest"]
        or document.id != row["id"]
        or document.calibration_id != row["calibration_id"]
        or document.observation_id != row["observation_id"]
        or intent.calibration_id != row["calibration_id"]
        or intent.observation_id != row["observation_id"]
        or document.objective != intent.objective
        or (cohort.workspace_id, cohort.account_id, cohort.campaign_id)
        != (row["workspace_id"], row["account_id"], row["campaign_id"])
        or utc(row["created_at"]) != document.created_at
        or utc(row["expires_at"]) != document.expires_at
    ):
        raise ValueError("initial preview row binding mismatch")
    return document


def preview_mandate_reference(
    row: Mapping[str, Any], document: InitialPreviewV1 | InitialPreviewV2
) -> tuple[str, int] | None:
    if bind_preview_row(row) != document:
        raise ValueError("initial preview document mismatch")
    intent: PreviewIntentV1 | PreviewIntentV2 = (
        PreviewIntentV1.model_validate(row["intent"])
        if isinstance(document, InitialPreviewV1)
        else PreviewIntentV2.model_validate(row["intent"])
    )
    if intent.mandate_id is None or intent.mandate_revision is None:
        return None
    return intent.mandate_id, intent.mandate_revision
