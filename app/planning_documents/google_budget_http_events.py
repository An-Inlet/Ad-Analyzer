"""Distinct admitted mock HTTP evidence; never a relabeled legacy fixture observation."""

from typing import Any, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.planning_documents.common import Digest, Id
from app.planning_documents.context import ReportingWindow
from app.planning_documents.events import VersionBinding
from app.planning_documents.google_budget_http_proof import (
    HTTP_PROFILE,
    GoogleBudgetHTTPProofV1,
    decoded,
)
from app.planning_documents.google_budget_hypothesis_comparison import (
    GoogleBudgetHypothesisComparisonV1,
)
from app.planning_documents.google_budget_owner_contracts import (
    GoogleDailyBudgetOwnerWitnessV1,
    _instant,
)
from app.planning_documents.google_budget_read import Query, ReadValue
from app.planning_documents.google_budget_read_projection import project_budget_rows
from app.publication.execution_contracts import ExecutionAccount


class BudgetHTTPIntent(VersionBinding):
    expected_event_sequence: int = Field(strict=True, ge=0)
    request_key: str = Field(strict=True, min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    profile_digest: Digest = HTTP_PROFILE

    @model_validator(mode="after")
    def exact(self) -> "BudgetHTTPIntent":
        if self.profile_digest != HTTP_PROFILE:
            raise ValueError("exact v24 HTTP profile required")
        return self

    def binding(self) -> VersionBinding:
        return VersionBinding.model_validate(
            {k: getattr(self, k) for k in VersionBinding.model_fields}
        )


def http_budget_witness(
    proof: GoogleBudgetHTTPProofV1,
    window: ReportingWindow,
    owner_key: str,
) -> GoogleDailyBudgetOwnerWitnessV1:
    proof = GoogleBudgetHTTPProofV1.model_validate(proof)
    ticket, account = proof.ticket, proof.ticket.account
    if window.ends_at_exclusive > ticket.prepared_at:
        raise ValueError("saved reporting window must precede acquisition")
    rows: dict[Query, list[dict[str, Any]]] = {}
    for page in proof.pages:
        values, _, _ = decoded(page, account.native_customer_id)
        rows.setdefault(page.query_kind, []).extend(values)
    scope = ExecutionAccount.model_validate(
        dict(
            workspace_id=account.workspace_id,
            account=dict(
                account_id=account.account_id,
                connection_id=account.connection_id,
                platform=account.platform,
            ),
            external_advertiser_id=account.native_customer_id,
            connection_version=account.connection_version,
        )
    )
    return project_budget_rows(
        account=scope,
        source=ticket.source_binding_digest,
        privacy=ticket.privacy_revision,
        window=window,
        proof_digest=proof.digest(),
        ticket_digest=ticket.digest(),
        expires=ticket.expires_at,
        started=proof.pages[0].requested_at,
        ended=proof.pages[-1].received_at,
        rows=rows,
        owner_key=owner_key,
        declared_scope=(
            "Mock HTTP Google v24 budget settings; provider authentication not verified."
        ),
    )


class GoogleBudgetHTTPObservationV1(VersionBinding, ReadValue):
    schema_version: Literal["inlet.google-budget-http-observation.v1"] = (
        "inlet.google-budget-http-observation.v1"
    )
    event_id: Id
    actor_id: Id
    recorded_at: AwareDatetime
    provenance: Literal["mock_http"] = "mock_http"
    provider_authentication: Literal["not_verified"] = "not_verified"
    current_reliance: Literal["not_assessed"] = "not_assessed"
    implementation: Literal["not_assessed"] = "not_assessed"
    comparison: GoogleBudgetHypothesisComparisonV1
    proof: GoogleBudgetHTTPProofV1
    finding: Literal["matches_hypothesis", "differs_from_hypothesis"]

    def binding(self) -> VersionBinding:
        return VersionBinding.model_validate(
            {k: getattr(self, k) for k in VersionBinding.model_fields}
        )

    @field_validator("recorded_at", mode="before")
    @classmethod
    def instant(cls, value: Any) -> Any:
        return _instant(value)

    @model_validator(mode="after")
    def exact(self) -> "GoogleBudgetHTTPObservationV1":
        comparison, ticket = self.comparison, self.proof.ticket
        if comparison.fresh is None:
            raise ValueError("HTTP observation needs acquired setting")
        if (
            comparison.binding != self.binding()
            or ticket.binding != self.binding()
            or ticket.privacy_revision != comparison.privacy_revision
            or ticket.source_binding_digest != comparison.source_binding_digest
            or self.recorded_at != comparison.compared_at
            or self.finding != comparison.status
            or http_budget_witness(
                self.proof, comparison.document.inputs.reporting_window, comparison.fresh.owner_key
            )
            != comparison.fresh
        ):
            raise ValueError("exact HTTP proof/comparison binding required")
        return self
