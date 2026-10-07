"""Non-authorizing original-versus-current Google total budget observations."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.publication.execution_contracts import Amount, Environment
from app.publication.provider_contracts import Digest, Id

EnvelopeReason = Literal[
    "original_total_creation_unavailable",
    "original_receipt_unavailable",
    "native_inventory_incomplete",
    "native_resource_unavailable",
    "native_budget_changed",
    "native_ownership_changed",
    "native_campaign_changed",
    "financial_basis_unqualified",
    "historical_liabilities_unverified",
]


class GoogleTotalEnvelopeViewV1(StrictModel):
    schema_version: Literal["inlet.google-total-envelope-observation.v1"] = (
        "inlet.google-total-envelope-observation.v1"
    )
    run_id: Id
    environment: Environment
    status: Literal["matching_configuration", "configuration_drift", "unavailable"]
    quantity: Literal["native_campaign_total_budget_setting_micros"] = (
        "native_campaign_total_budget_setting_micros"
    )
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    campaign_starts_at: AwareDatetime
    campaign_ends_at: AwareDatetime
    original_total_micros: Amount
    observed_total_micros: Amount | None = None
    reservation_micros: Amount
    reservation_state: Literal["held", "settled", "superseded"]
    original_binding_digest: Digest
    inventory_digest: Digest
    observation_started_at: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    reasons: list[EnvelopeReason] = Field(min_length=2, max_length=9)
    financial_basis: Literal["unqualified"] = "unqualified"
    financial_upper_micros: None = None
    spending_authority: Literal["none"] = "none"
    settlement: Literal["not_assessed"] = "not_assessed"
    outside_writer_prevention: Literal["not_asserted"] = "not_asserted"
    portfolio_coverage: Literal["single_original_run_only"] = "single_original_run_only"

    @model_validator(mode="after")
    def consistent(self) -> "GoogleTotalEnvelopeViewV1":
        from zoneinfo import ZoneInfo

        ZoneInfo(self.time_zone)
        if (
            self.campaign_starts_at >= self.campaign_ends_at
            or not self.observation_started_at <= self.observed_at < self.expires_at
            or len(set(self.reasons)) != len(self.reasons)
            or not {"financial_basis_unqualified", "historical_liabilities_unverified"}.issubset(
                self.reasons
            )
            or (
                self.status == "matching_configuration"
                and (
                    self.observed_total_micros != self.original_total_micros
                    or len(self.reasons) != 2
                )
            )
            or (self.status != "matching_configuration" and len(self.reasons) == 2)
        ):
            raise ValueError("inconsistent non-authorizing envelope observation")
        return self
