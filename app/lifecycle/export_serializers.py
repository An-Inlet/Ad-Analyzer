"""Customer export v1 domain allowlists. Never serialize arbitrary ORM state."""

import json
import re
from collections.abc import Mapping
from typing import Annotated, Any

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.campaign_review.contracts import ReviewArtifact
from app.commerce.evidence import digest as assessment_digest
from app.crm.schemas import CrmEvent
from app.goals.schemas import GoalDefinition
from app.intelligence.schemas import PAYLOAD_MODELS, RecordKind
from app.lifecycle.export_domains import SettlementEvidence
from app.lifecycle.inventory import scalar
from app.lifecycle.registry import TABLES
from app.mandates.schemas import ActionDraft, MandateDefinition
from app.outcomes.owned_contracts import OwnedAssessment
from app.publication.activation_contracts import (
    ActivationReceipt,
    ActivationRequest,
    ActivationResponse,
)
from app.publication.activation_review import ActivationExecutionReview
from app.publication.contracts import BoundRequest, PublishPlan, PublishReceipt, fingerprint
from app.publication.coordinator_contracts import (
    CreationExecutionReview,
    CreationReceipt,
    CreationRequest,
    CreationResponse,
)
from app.publication.execution_contracts import (
    ExposureEvidence,
    NormalizedProviderReceipt,
    ProviderMandatePolicy,
)
from app.publication.optimization_contracts import (
    OptimizationReceipt,
    OptimizationRequest,
    OptimizationResponse,
)
from app.publication.optimization_execution_contracts import OptimizationExecutionReview
from app.publication.provider_contracts import ProviderPublicationReview, ProviderPublishPlan
from app.publication.social_review_contracts import (
    LegacySocialConfigurationDocumentV1,
    SocialConfigurationDocument,
)

# Explicit customer-facing structured fields. Free-form fields remain bounded JSON,
# not arbitrary columns or provider transport responses. Typed historical fields use
# their versioned product contracts and reject unknown/invalid persisted documents.
JSON_FIELDS: dict[str, tuple[str, ...]] = {
    "action_outcome_assessments": ("assessment",),
    "analysis_runs": ("blocking_reasons", "decision_brief", "retry_history"),
    "commerce_snapshots": ("result",),
    "commerce_measurement_publications": ("manifest",),
    "crm_events": ("normalized_payload",),
    "customer_campaign_revisions": ("artifact",),
    "customer_social_configuration_reviews": ("document",),
    "customer_goal_revisions": ("definition",),
    "customer_lifecycle_requests": ("blockers",),
    "execution_audits": ("validation_errors",),
    "intelligence_records": ("data",),
    "intelligence_revisions": ("before_data", "after_data"),
    "lead_attribution": ("attribution_data",),
    "mandate_actions": ("draft",),
    "publication_plans": ("document",),
    "provider_reviews": ("review", "plan"),
    "provider_execution_revisions": ("policy",),
    "provider_execution_reviews": ("document",),
    "provider_exposure_reservations": ("evidence", "settled_evidence"),
    "provider_execution_attempts": ("request",),
    "provider_execution_responses": ("response",),
    "provider_execution_receipts": ("receipt", "projection"),
    "publication_steps": ("request", "receipt"),
    "publication_receipts": ("request", "receipt"),
    "recommendations": ("supporting_metrics", "planned_action"),
    "shopify_orders": ("products",),
    "shopify_privacy_requests": ("order_keys", "commerce_keys"),
    "spending_mandate_revisions": ("definition",),
    "workspace_configurations": ("analysis", "automation", "notifications", "branding"),
    "workspace_findings": ("supporting_metrics",),
    "workspace_integrations": ("configuration",),
}
ADDITIONS: dict[str, tuple[str, ...]] = {
    "automation_control_audits": ("key",),
    "commerce_entries": ("order_key",),
    "commerce_measurement_publications": ("completion_digest", "manifest_digest"),
    "commerce_orders": ("order_key", "privacy_key", "customer_key"),
    "commerce_shop_aliases": ("shop_domain",),
    "commerce_source_links": ("order_key",),
    "commerce_stores": ("shop_domain",),
    "crm_events": ("payload_hash",),
    "customer_billing_events": ("body_hash",),
    "customer_campaign_revisions": ("digest",),
    "customer_lifecycle_steps": ("evidence_digest",),
    "customer_workspace_billing": ("checkout_id",),
    "execution_audits": ("rollback_instructions",),
    "mandate_actions": ("digest",),
    "meta_oauth_states": ("phase",),
    "publication_plans": ("digest", "activation_digest"),
    "publication_receipts": ("digest",),
    "recommendation_audits": ("reason",),
    "recommendations": ("rationale",),
    "shopify_connections": ("shop_domain", "shop_name"),
    "shopify_oauth_states": ("shop_domain",),
    "shopify_orders": ("order_key",),
    "shopify_privacy_identities": ("shop_domain",),
    "shopify_privacy_requests": ("customer_key",),
    "shopify_tombstones": ("order_key",),
    "web_analytics_events": (
        "user_pseudo_id_digest",
        "subject_id_digest",
        "session_id_digest",
        "click_id_digest",
    ),
    "workspace_automation_controls": ("key",),
    "workspace_findings": ("message",),
}
TYPED: dict[tuple[str, str], type[BaseModel]] = {
    ("action_outcome_assessments", "assessment"): OwnedAssessment,
    ("crm_events", "normalized_payload"): CrmEvent,
    ("customer_goal_revisions", "definition"): GoalDefinition,
    ("spending_mandate_revisions", "definition"): MandateDefinition,
    ("mandate_actions", "draft"): ActionDraft,
    ("customer_campaign_revisions", "artifact"): ReviewArtifact,
    ("publication_plans", "document"): PublishPlan,
    ("provider_reviews", "review"): ProviderPublicationReview,
    ("provider_reviews", "plan"): ProviderPublishPlan,
    ("provider_execution_revisions", "policy"): ProviderMandatePolicy,
    ("provider_exposure_reservations", "evidence"): ExposureEvidence,
    ("provider_execution_receipts", "projection"): NormalizedProviderReceipt,
    ("publication_steps", "request"): BoundRequest,
    ("publication_steps", "receipt"): PublishReceipt,
    ("publication_receipts", "request"): BoundRequest,
    ("publication_receipts", "receipt"): PublishReceipt,
}
ADAPTERS: dict[tuple[str, str], TypeAdapter[Any]] = {
    ("customer_social_configuration_reviews", "document"): TypeAdapter(
        Annotated[
            SocialConfigurationDocument | LegacySocialConfigurationDocumentV1,
            Field(discriminator="schema_version"),
        ]
    ),
    ("provider_execution_reviews", "document"): TypeAdapter(
        Annotated[
            CreationExecutionReview | ActivationExecutionReview | OptimizationExecutionReview,
            Field(discriminator="schema_version"),
        ]
    ),
    ("provider_exposure_reservations", "settled_evidence"): TypeAdapter(
        ExposureEvidence | SettlementEvidence
    ),
    ("provider_execution_attempts", "request"): TypeAdapter(
        CreationRequest | ActivationRequest | OptimizationRequest
    ),
    ("provider_execution_responses", "response"): TypeAdapter(
        ActivationResponse | CreationResponse
    ),
    ("provider_execution_receipts", "receipt"): TypeAdapter(
        CreationReceipt | ActivationReceipt | OptimizationReceipt
    ),
}
# Responses share an identical shape: their persisted domain-separated digest,
# not union order, selects the strict schema.
RESPONSE_ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "inlet.provider-response.v1": TypeAdapter(CreationResponse),
    "inlet.activation-response.v1": TypeAdapter(ActivationResponse),
    "inlet.optimization-response.v1": TypeAdapter(OptimizationResponse),
}
# These are deliberately not customer-owned business content. New omissions that
# do not match this explicit set become unsupported omissions, never successful export.
INTERNAL = {
    "export_privacy_revision",
    "request_key",
    "key_digest",
    "request_digest",
    "customer_request_key",
    "checkout_key",
    "idempotency_key",
    "fence",
    "lease_until",
    "ack_digest",
    "grant_digest",
    "session_digest",
    "actor_digest",
    "oauth_state_digest",
    "cursor",
    "seen_cursors",
    "staged",
    "accounts",
    "error_message",
    "encrypted_grant",
    "encrypted_credentials",
    "encrypted_progress",
    "secret_manager_reference",
    "checkout_url",
    "principal",
}
INTERNAL_TABLE_FIELDS = {
    ("meta_detail_staged_pages", "payload"),
    ("provider_qualifications", "evidence"),
}
SECRET_KEY = re.compile(
    r"(?:secret|password|credential|authorization|cookie|session_digest|csrf|"
    r"(?:access|refresh|id)_token|encrypted|private_key)",
    re.I,
)


def fields(table: str) -> tuple[str, ...]:
    return tuple(
        field
        for field in dict.fromkeys(
            (*TABLES[table].fields, *ADDITIONS.get(table, ()), *JSON_FIELDS.get(table, ()))
        )
        if field not in INTERNAL
    )


def exclusion(table: str, column: str) -> str:
    if column in INTERNAL or (table, column) in INTERNAL_TABLE_FIELDS:
        return "security_or_internal"
    if column == "digest" and table.endswith(("authorizations", "oauth_states")):
        return "security_or_internal"
    return "unsupported_customer_field"


def bounded_json(value: Any, depth: int = 0) -> Any:
    if depth > 16:
        raise ValueError("unsupported structured depth")
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list) and len(value) <= 10000:
        return [bounded_json(item, depth + 1) for item in value]
    if isinstance(value, dict) and len(value) <= 1000:
        result = {}
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 256 or SECRET_KEY.search(key):
                raise ValueError("structured field not exportable")
            result[key] = bounded_json(item, depth + 1)
        return result
    raise ValueError("unsupported structured value")


def bind_document(
    table: str, field: str, row: Mapping[str, Any], document: BaseModel, raw: Any
) -> None:
    """Bind added domains to owned scalar lineage, never trust JSON scope alone."""
    if isinstance(document, (SocialConfigurationDocument, LegacySocialConfigurationDocumentV1)):
        account = document.request.account
        if (
            account.workspace_id != row["workspace_id"]
            or account.account.account_id != row["account_id"]
            or account.account.connection_id != row["integration_id"]
            or document.request.draft_id != row["draft_id"]
            or document.request.draft_revision != row["source_revision"]
            or document.digest() != row["digest"]
        ):
            raise ValueError("social configuration row ownership mismatch")
    elif isinstance(document, OwnedAssessment):
        expected = {
            "workspace_id": document.workspace_id,
            "environment": document.environment,
            "publication_id": document.publication_id,
            "generation": document.generation,
            "privacy_epoch": document.privacy_epoch,
            "policy_id": document.policy_id,
            "policy_digest": document.policy_digest,
            "input_digest": document.input_digest,
            "attempt_id": document.receipt.attempt_id,
            "receipt_id": document.receipt.receipt_id,
            "receipt_sequence": document.receipt.sequence,
            "receipt_digest": document.receipt.receipt_digest,
            "projection_digest": document.receipt.projection_digest,
            "assessment_digest": assessment_digest(raw),
        }
        if any(row[key] != value for key, value in expected.items()):
            raise ValueError("assessment row ownership mismatch")
    elif isinstance(document, OptimizationExecutionReview):
        scope = document.plan.intent.scope
        if (
            scope.workspace_id != row["workspace_id"]
            or scope.account.account_id != row["account_id"]
            or scope.account.connection_id != row["integration_id"]
            or document.plan.intent.mandate.consent_id != row["consent_id"]
            or document.digest() != row["digest"]
            or document.plan.digest() != row["plan_digest"]
            or row["source_draft_id"] is not None
            or row["source_revision"] is not None
        ):
            raise ValueError("optimization review row ownership mismatch")
    elif isinstance(document, OptimizationRequest):
        if (
            document.intent.scope.workspace_id != row["workspace_id"]
            or document.action_id != row["run_id"]
            or document.attempt_id != row["id"]
            or row["step_id"] != "optimize"
        ):
            raise ValueError("optimization request row ownership mismatch")
    elif isinstance(document, OptimizationReceipt):
        if (
            document.scope.workspace_id != row["workspace_id"]
            or document.attempt_id != row["attempt_id"]
            or fingerprint("inlet.optimization-receipt.v1", raw) != row["digest"]
        ):
            raise ValueError("optimization receipt row ownership mismatch")
    elif isinstance(document, ActivationExecutionReview):
        if (
            document.plan.account.workspace_id != row["workspace_id"]
            or document.digest() != row["digest"]
            or document.plan.digest() != row["plan_digest"]
            or document.plan.account.account.account_id != row["account_id"]
            or document.plan.account.account.connection_id != row["integration_id"]
        ):
            raise ValueError("activation review row ownership mismatch")
    elif isinstance(document, ActivationRequest):
        if (
            document.account.workspace_id != row["workspace_id"]
            or document.run_id != row["run_id"]
            or document.target.step_id != row["step_id"]
        ):
            raise ValueError("activation request row ownership mismatch")
    elif isinstance(document, ActivationResponse):
        if row["digest"] not in {
            fingerprint("inlet.activation-response.v1", raw),
            fingerprint("inlet.provider-response.v1", raw),
        }:
            raise ValueError("response content digest mismatch")
    elif isinstance(document, ActivationReceipt):
        if (
            document.account.workspace_id != row["workspace_id"]
            or fingerprint("inlet.activation-receipt.v1", raw) != row["digest"]
        ):
            raise ValueError("activation receipt row ownership mismatch")
    elif isinstance(document, SettlementEvidence):
        expected = {
            "id": document.snapshot.reservation_id,
            "workspace_id": document.snapshot.workspace_id,
            "ledger_id": document.snapshot.ledger_id,
            "environment": document.snapshot.environment,
            "budget_owner_key": document.snapshot.budget_owner_key,
            "amount_micros": document.snapshot.amount_micros,
            "state": "settled",
        }
        if any(row[key] != value for key, value in expected.items()):
            raise ValueError("settlement row ownership mismatch")


def serialize(table: str, row: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    output, missing = {}, []
    for field in fields(table):
        value = row[field]
        try:
            if field in JSON_FIELDS.get(table, ()) and value is not None:
                if (
                    table == "action_outcome_assessments"
                    and field == "assessment"
                    and len(
                        json.dumps(
                            value, sort_keys=True, separators=(",", ":"), allow_nan=False
                        ).encode()
                    )
                    > 256 * 1024
                ):
                    raise ValueError("assessment exceeds export bound")
                model = TYPED.get((table, field))
                if table in {"intelligence_records", "intelligence_revisions"}:
                    model = PAYLOAD_MODELS[RecordKind(row["kind"])]
                value = bounded_json(value)
                if model is not None:
                    document = model.model_validate(value)
                    bind_document(table, field, row, document, value)
                    value = document.model_dump(mode="json")
                adapter = ADAPTERS.get((table, field))
                if (table, field) == ("provider_execution_responses", "response"):
                    adapter = next(
                        (
                            candidate
                            for domain, candidate in RESPONSE_ADAPTERS.items()
                            if fingerprint(domain, value) == row["digest"]
                        ),
                        None,
                    )
                    if adapter is None:
                        raise ValueError("unsupported response digest")
                if adapter is not None:
                    document = adapter.validate_python(value)
                    bind_document(table, field, row, document, value)
                    value = document.model_dump(mode="json")
                json.dumps(value, allow_nan=False)
            else:
                value = scalar(value)
            output[field] = value
        except (ValueError, TypeError, KeyError, ValidationError):
            missing.append(field)
    return output, missing
