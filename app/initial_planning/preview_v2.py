"""Explicit unqualified preview version; legacy v1 bytes and handoff are unchanged."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, TypeAdapter, model_validator

from app.initial_planning.contracts import EfficiencyObjectiveV1, Frozen, InitialPreviewV1
from app.initial_planning.native_budget_contracts import NativeBudgetObservationV1
from app.publication.contracts import fingerprint
from app.publication.provider_contracts import Digest


class InitialPreviewV2(Frozen):
    schema_version: Literal["inlet.initial-efficiency-preview.v2"] = (
        "inlet.initial-efficiency-preview.v2"
    )
    environment: Literal["contract_test", "live"]
    profile_digest: Digest
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    calibration_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    observation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    objective: EfficiencyObjectiveV1
    policy_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    recommendation_status: Literal["proposed", "hold", "insufficient"]
    direction: Literal["increase", "decrease", "none"]
    before_budget_micros: int | None = Field(default=None, strict=True, gt=0)
    after_budget_micros: int | None = Field(default=None, strict=True, gt=0)
    native_observation: NativeBudgetObservationV1 | None = None
    reasons: tuple[str, ...] = Field(max_length=20)
    created_at: AwareDatetime
    expires_at: AwareDatetime
    review_available: Literal[False] = False
    handoff_reason: Literal["initial_preview_native_read_unqualified"] = (
        "initial_preview_native_read_unqualified"
    )
    spending_authorized: Literal[False] = False
    empirical_qualification: Literal[False] = False

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))

    @model_validator(mode="after")
    def exact_or_absent(self) -> "InitialPreviewV2":
        values = (self.before_budget_micros, self.after_budget_micros, self.native_observation)
        if any(v is not None for v in values) and any(v is None for v in values):
            raise ValueError("native amounts require complete current native evidence")
        if (self.recommendation_status == "proposed") != (
            self.direction in {"increase", "decrease"}
        ):
            raise ValueError("recommendation direction inconsistent")
        if self.recommendation_status == "insufficient" and any(v is not None for v in values):
            raise ValueError("insufficient evidence cannot carry native amounts")
        if self.before_budget_micros is not None and self.after_budget_micros is not None:
            delta = self.after_budget_micros - self.before_budget_micros
            if (
                (self.direction == "increase" and delta <= 0)
                or (self.direction == "decrease" and delta >= 0)
                or (self.direction == "none" and delta != 0)
            ):
                raise ValueError("native amount direction inconsistent")
        if not self.created_at < self.expires_at:
            raise ValueError("bounded preview lifetime required")
        native = self.native_observation
        if native is not None and (
            native.request.profile_digest != self.profile_digest
            or native.request.environment != self.environment
            or native.request.cohort != self.objective.cohort
            or native.request.goal_id != self.objective.goal_id
            or native.request.goal_revision != self.objective.goal_revision
            or native.unsupported_reasons
            or self.before_budget_micros != native.amount_micros
            or self.after_budget_micros is None
            or self.after_budget_micros % 10 ** (6 - native.currency_exponent)
            or self.created_at < native.observed_at
            or self.expires_at > native.expires_at
        ):
            raise ValueError("preview native observation binding mismatch")
        if (self.expires_at - self.created_at).total_seconds() > 300:
            raise ValueError("preview lifetime exceeds bound")
        return self


InitialPreview = Annotated[
    InitialPreviewV1 | InitialPreviewV2, Field(discriminator="schema_version")
]


def parse_initial_preview(document: object) -> InitialPreviewV1 | InitialPreviewV2:
    """Pure strict version dispatch, never an ownership or financial authorization."""
    return TypeAdapter(InitialPreview).validate_python(document)


class PreviewIntentV2(Frozen):
    """Server-resolved persisted intent, never accepted as browser proof JSON."""

    schema_version: Literal["inlet.initial-preview-intent.v2"] = "inlet.initial-preview-intent.v2"
    objective: EfficiencyObjectiveV1
    calibration_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    observation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    environment: Literal["contract_test", "live"]
    profile_digest: Digest
    goal_digest: Digest
    native_option_id: Digest | None = None
    mandate_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    mandate_revision: int | None = Field(default=None, strict=True, gt=0)

    @model_validator(mode="after")
    def exact_selection(self) -> "PreviewIntentV2":
        fields = (self.native_option_id, self.mandate_id, self.mandate_revision)
        if any(v is not None for v in fields) and any(v is None for v in fields):
            raise ValueError("exact native selection and mandate reference required")
        return self
