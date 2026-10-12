"""Derive only queried budget/campaign fields; unqueried settings remain unavailable."""

from datetime import datetime
from typing import Any

from app.planning_catalog.contracts import TargetCatalogV1
from app.planning_catalog.metadata_contracts import (
    PlanningMetadataV1,
    TargetCatalogV2,
    canonical_key,
    selection_key,
    settings_key,
)
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.context import ReportingWindow
from app.planning_documents.google_budget_owner_contracts import (
    GoogleDailyBudgetOwnerWitnessV1,
    derive_google_daily_budget_owner,
)
from app.planning_documents.google_budget_read import GoogleBudgetReadProofV1, Query, _integer
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount


def budget_read_witness(
    proof: GoogleBudgetReadProofV1, owner_key: str
) -> GoogleDailyBudgetOwnerWitnessV1:
    proof = GoogleBudgetReadProofV1.model_validate(proof)
    ticket = proof.ticket
    return project_budget_rows(
        account=ticket.account, source=ticket.source_digest(), privacy=ticket.privacy_revision,
        window=ticket.reporting_window, proof_digest=proof.digest(), ticket_digest=ticket.digest(),
        expires=ticket.expires_at, started=proof.pages[0].requested_at,
        ended=proof.pages[-1].received_at, rows=proof.rows(), owner_key=owner_key,
        declared_scope="Injected fixture Google budget settings and full campaign membership.",
    )


def project_budget_rows(
    *, account: ExecutionAccount, source: str, privacy: int, window: ReportingWindow,
    proof_digest: str, ticket_digest: str, expires: datetime, started: datetime,
    ended: datetime, rows: dict[Query, list[dict[str, Any]]], owner_key: str, declared_scope: str,
) -> GoogleDailyBudgetOwnerWitnessV1:
    """Pure field projection; callers must validate the exact versioned transcript first."""
    customer = rows["customer"][0]
    common = dict(
        workspace_id=account.workspace_id,
        account_id=account.account.account_id,
        connection_id=account.account.connection_id,
        platform="google_ads",
        connection_version=account.connection_version,
        source_binding_digest=source,
        reporting_starts_at=window.starts_at,
        reporting_ends_at=window.ends_at_exclusive,
        observation_started_at=started,
        observed_at=ended,
        expires_at=expires,
    )
    budgets = {row["resourceName"]: row for row in rows["campaignBudget"]}

    def key(kind: str, resource: str) -> str:
        return fingerprint(
            "inlet.planning-target.v1", dict(source=source, kind=kind, native_id=resource)
        )

    targets, entities = [], []
    unavailable = ("channel", "bidding_strategy", "starts_native", "ends_native", "name")
    for campaign in rows["campaign"]:
        budget = budgets[campaign["campaignBudget"]]
        targets.append(
            dict(
                selection_key=key("campaign", campaign["resourceName"]),
                kind="campaign",
                parent_selection_key=None,
                budget_owner_key=key("budget", budget["resourceName"]),
                name=None,
                name_source="unavailable",
                unavailable_fields=unavailable,
                reasons=("narrow_budget_read_profile",),
                settings=dict(
                    platform="google_ads",
                    status=campaign["status"],
                    channel=None,
                    bidding_strategy=None,
                    starts_native=None,
                    ends_native=None,
                    budget_amount_micros=_integer(budget["amountMicros"]),
                    budget_total_amount_micros=None,
                    budget_period=budget["period"],
                    budget_status=budget["status"],
                    budget_type=budget["type"],
                    budget_explicitly_shared=budget["explicitlyShared"],
                    budget_reference_count=_integer(budget["referenceCount"]),
                ),
            )
        )
        entities.append(
            dict(
                kind="campaign",
                reference=dict(
                    platform="google_ads",
                    advertiser_id=account.external_advertiser_id,
                    entity_id=campaign["resourceName"].rsplit("/", 1)[1],
                    parent_campaign_id=None,
                ),
                name=None,
                name_status="missing",
                status=campaign["status"],
                entity_type=None,
            )
        )
    native = TargetCatalogV1.model_validate(
        dict(
            **common,
            inventory_digest=proof_digest,
            currency=customer["currencyCode"],
            time_zone=customer["timeZone"],
            targets=targets,
            coverage=(
                dict(
                    kind="campaign",
                    status="complete",
                    observed_count=len(targets),
                    scope="provider_campaigns",
                    reasons=(),
                ),
                dict(
                    kind="adgroup",
                    status="unavailable",
                    observed_count=0,
                    scope="not_collected",
                    reasons=("adgroups_not_collected",),
                ),
            ),
        )
    )
    metadata = PlanningMetadataV1.model_validate(
        dict(
            **common,
            native_inventory_digest=proof_digest,
            request_digest=ticket_digest,
            entities=entities,
            coverage=(
                dict(
                    kind="campaign",
                    status="complete",
                    count=len(entities),
                    scope="provider_campaigns",
                    reasons=(),
                ),
                dict(
                    kind="adgroup",
                    status="partial",
                    count=0,
                    scope="provider_adgroups",
                    reasons=("adgroups_not_collected",),
                ),
            ),
        )
    )
    composite = fingerprint(
        "inlet.planning-catalog-composite.v1",
        dict(native_inventory_digest=proof_digest, metadata_digest=metadata.digest()),
    )
    bound = {t.selection_key: t for t in native.targets}
    catalog = TargetCatalogV2.model_validate(
        dict(
            native_observation=native,
            metadata_observation=metadata,
            composite_digest=composite,
            expires_at=expires,
            targets=[
                dict(
                    canonical_entity_key=canonical_key(metadata, entity),
                    selection_key=selection_key(canonical_key(metadata, entity), source, composite),
                    entity=entity,
                    native_settings_key=settings_key(source, entity),
                    budget_owner_key=bound[settings_key(source, entity)].budget_owner_key,
                )
                for entity in metadata.entities
            ],
        )
    )
    evidence = CatalogEvidence.model_validate(
        dict(
            catalog=catalog,
            reference=dict(
                key="catalog:google-budget-read",
                workspace_id=account.workspace_id,
                kind="native_catalog",
                account=dict(
                    workspace_id=account.workspace_id,
                    account_id=account.account.account_id,
                    connection_id=account.account.connection_id,
                    connection_version=account.connection_version,
                    platform="google_ads",
                ),
                document_schema=catalog.schema_version,
                document_digest=composite,
                source_binding_digest=source,
                source_revision=account.connection_version,
                privacy_revision=privacy,
                reporting_window=window,
                observation_started_at=native.observation_started_at,
                observed_at=native.observed_at,
                expires_at=expires,
                coverage="partial",
                declared_scope=declared_scope,
                reasons=("unqueried_campaign_settings", "adgroups_not_collected"),
                metric_basis=(
                    "Settings only; no performance metrics or authenticated provider claim."
                ),
            ),
        )
    )
    return derive_google_daily_budget_owner(evidence, owner_key)
