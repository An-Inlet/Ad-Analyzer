"""Strict aggregate export bindings; never export session credentials or arbitrary JSON."""

import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from app.initial_planning.contracts import (
    CalibrationReportV1,
    EfficiencyObjectiveV1,
    InitialPreviewV1,
    ObservationV1,
    PreviewIntentV1,
)
from app.publication.contracts import fingerprint
from app.shopify.security import utc


def bind_initial_document(
    table: str, field: str, row: Mapping[str, Any], document: BaseModel
) -> bool:
    if table not in {"initial_observations", "initial_calibration_runs", "initial_plan_previews"}:
        return False
    if len(json.dumps(document.model_dump(mode="json"), allow_nan=False).encode()) > 256 * 1024:
        raise ValueError("initial document exceeds bounded export")
    if isinstance(document, PreviewIntentV1):
        preview = InitialPreviewV1.model_validate(row["document"])
        if (
            document.calibration_id != row["calibration_id"]
            or document.observation_id != row["observation_id"]
            or document.objective != preview.objective
        ):
            raise ValueError("initial preview intent mismatch")
        cohort = document.objective.cohort
    elif isinstance(document, EfficiencyObjectiveV1):
        if document.digest() != row["objective_digest"]:
            raise ValueError("initial objective mismatch")
        cohort = document.cohort
    elif isinstance(document, (ObservationV1, CalibrationReportV1, InitialPreviewV1)):
        if (
            document.id != row["id"]
            or document.expires_at != utc(row["expires_at"])
            or fingerprint(document.schema_version, document.model_dump(mode="json"))
            != row["document_digest"]
        ):
            raise ValueError("initial document binding mismatch")
        if isinstance(document, ObservationV1):
            cohort = document.cohort
            exact = {
                "environment": document.environment,
                "completion_id": document.completion_id,
                "generation": document.generation,
                "privacy_revision": document.privacy_revision,
                "cohort_digest": document.cohort.digest(),
                "retention_policy_digest": document.retention_policy_digest,
            }
            if document.captured_at != utc(row["captured_at"]):
                raise ValueError("initial observation capture mismatch")
        elif isinstance(document, CalibrationReportV1):
            cohort = document.cohort
            exact = {
                "environment": document.environment,
                "objective_digest": document.objective_digest,
                "policy_digest": document.policy_digest,
                "input_digest": document.input_digest,
            }
            if document.evaluated_at != utc(row["created_at"]):
                raise ValueError("initial calibration time mismatch")
        else:
            cohort = document.objective.cohort
            exact = {
                "calibration_id": document.calibration_id,
                "observation_id": document.observation_id,
                "native_state_digest": document.native_state_digest,
            }
            if document.created_at != utc(row["created_at"]):
                raise ValueError("initial preview time mismatch")
        if any(row[key] != value for key, value in exact.items()):
            raise ValueError("initial document scalar mismatch")
    else:
        raise ValueError("unknown initial planning export document")
    if (cohort.workspace_id, cohort.account_id, cohort.campaign_id) != (
        row["workspace_id"],
        row["account_id"],
        row["campaign_id"],
    ):
        raise ValueError("initial document ownership mismatch")
    return True
