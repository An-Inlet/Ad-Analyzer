"""Explicit synthetic search pages, never authenticated provider captures."""

import copy
import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import VersionBinding
from app.planning_documents.google_budget_read import QUERIES, GoogleBudgetReadTicketV1
from app.publication.execution_contracts import ExecutionAccount


def ticket(document: PlanVersion, account: ExecutionAccount) -> GoogleBudgetReadTicketV1:
    assert document.google_budget_owner_review is not None
    review = document.google_budget_owner_review.reviews[0]
    action = next(a for a in document.actions if a.key == review.action_key)
    return GoogleBudgetReadTicketV1(
        nonce="f" * 32,
        binding=VersionBinding(
            workspace_id=document.inputs.workspace_id,
            plan_id=document.inputs.plan_id,
            version=document.version,
            document_digest=document.digest(),
            action_key=action.key,
            action_digest=action.digest(),
        ),
        account=account,
        privacy_revision=review.witness.catalog_evidence.reference.privacy_revision,
        reporting_window=document.inputs.reporting_window,
        prepared_at=document.generated_at + timedelta(seconds=1),
        expires_at=document.generated_at + timedelta(minutes=4),
    )


class Search:
    def __init__(self, customer: str, budget_id: str = "2", amount: int = 1) -> None:
        prefix = "customers/" + customer
        self.data: dict[str, list[dict[str, Any]]] = {
            "customer": [
                dict(
                    customer=dict(
                        resourceName=prefix,
                        currencyCode="USD",
                        timeZone="UTC",
                        status="ENABLED",
                        manager=False,
                    )
                )
            ],
            "campaign": [
                dict(
                    campaign=dict(
                        resourceName=prefix + "/campaigns/" + str(i),
                        campaignBudget=prefix + "/campaignBudgets/" + budget_id,
                        status="ENABLED" if i == 1 else "PAUSED",
                    )
                )
                for i in (1, 2)
            ],
            "campaignBudget": [
                dict(
                    campaignBudget=dict(
                        resourceName=prefix + "/campaignBudgets/" + budget_id,
                        amountMicros=str(amount),
                        explicitlyShared=True,
                        referenceCount="2",
                        period="DAILY",
                        status="ENABLED",
                        type="STANDARD",
                    )
                )
            ],
        }
        self.calls: list[tuple[str, str | None]] = []
        self.override: Callable[[str, str | None], str] | None = None

    def __call__(self, ticket: GoogleBudgetReadTicketV1, query: str, cursor: str | None) -> str:
        assert ticket.api_version == "v22" and ticket.provenance == "injected_fixture"
        kind = next(k for k, value in QUERIES.items() if value == query)
        self.calls.append((kind, cursor))
        if self.override:
            return self.override(kind, cursor)
        rows = copy.deepcopy(self.data[kind])
        if kind == "campaign":
            assert cursor in (None, "fixture-page-2")
            return json.dumps(
                dict(results=rows[:1], nextPageToken="fixture-page-2")
                if cursor is None
                else dict(results=rows[1:])
            )
        assert cursor is None
        return json.dumps(dict(results=rows))
