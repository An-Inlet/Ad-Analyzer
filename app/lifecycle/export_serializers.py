"""Customer export v1 domain allowlists. Never serialize arbitrary ORM state."""

import json
import re
from collections.abc import Mapping
from typing import Annotated, Any

from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.billing.offers import (
    BoundOfferV1,
    OfferProfileV1,
    OfferQualificationV1,
)
from app.billing.offers import (
    digest as offer_digest,
)
from app.campaign_performance.presence_export import PresenceExportContext
from app.campaign_performance.selected_export import SelectedExportContext
from app.campaign_review.contracts import ReviewArtifact
from app.commerce.evidence import digest as assessment_digest
from app.commerce.publication_contracts import MANIFEST, ManifestBasis, bind_manifest
from app.crm.schemas import CrmEvent
from app.goals.schemas import GoalDefinition
from app.initial_planning.automatic_contracts import (
    InitialReportedRuleCandidateV1,
    InitialReportedRuleWorkV1,
)
from app.initial_planning.budget_mandate_contracts import BudgetMandatePreparationV1
from app.initial_planning.contracts import (
    CalibrationReportV1,
    EfficiencyObjectiveV1,
    ObservationV1,
    PreviewIntentV1,
)
from app.initial_planning.export import bind_initial_document
from app.initial_planning.preview_v2 import InitialPreview, PreviewIntentV2
from app.initial_planning.review_export import export_review_link
from app.initial_planning.review_v2_export import export_execution_proof
from app.intelligence.schemas import PAYLOAD_MODELS, RecordKind
from app.lifecycle.export_domains import SettlementEvidence
from app.lifecycle.inventory import scalar
from app.lifecycle.registry import PRIVATE_STAGING_TABLES, TABLES
from app.mandates.schemas import ActionDraft, MandateDefinition
from app.optimization_candidates.contracts import CandidateDecision, CandidateWork
from app.optimization_candidates.documents import DECISION_DOCUMENT_ADAPTER, WORK_DOCUMENT_ADAPTER
from app.optimization_candidates.selection_contracts import CandidateWorkV2
from app.outcomes.feedback import FeedbackContribution
from app.outcomes.owned_contracts import OwnedAssessment
from app.outcomes.owned_v3 import OwnedV3Assessment
from app.production_runtime.optimization_origin_contracts import OptimizationMandatePreparationV1
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
from app.publication.google_completion_contracts import GoogleCompletionDocument
from app.publication.google_execution_completion_contracts import GoogleExecutionCompletionV2
from app.publication.optimization_contracts import (
    OptimizationReceipt,
    OptimizationRequest,
    OptimizationResponse,
)
from app.publication.optimization_execution_contracts import OptimizationExecutionReview
from app.publication.provider_contracts import ProviderPublicationReview, ProviderPublishPlan
from app.publication.replacement_contracts import RepeatOptimizationReview, ReplacementAuditDocument
from app.publication.social_review_contracts import (
    LegacySocialConfigurationDocumentV1,
    SocialConfigurationDocument,
)
from app.publication.tiktok_linked_review_contracts import LinkedPushConfigurationDocumentV1
from app.reported_feedback.candidate_contracts import ReportedRuleCandidateV1, ReportedRuleWorkV1
from app.reported_feedback.contracts import (
    OperationalReportedComparisonV1,
    ReportedAcquisitionRequestV1,
    ReportedFeedbackPreviewV1,
    ReportedWindowCapsuleV1,
)
from app.reported_feedback.export import bind_reported_document
from app.shopify.security import utc

# Explicit customer-facing structured fields. Free-form fields remain bounded JSON,
# not arbitrary columns or provider transport responses. Typed historical fields use
# their versioned product contracts and reject unknown/invalid persisted documents.
JSON_FIELDS: dict[str, tuple[str, ...]] = {
    "reported_feedback_jobs": ("document",),
    "reported_window_capsules": ("document",),
    "reported_action_comparisons": ("document",),
    "reported_feedback_slots": ("document",),
    "initial_observations": ("document",),
    "initial_calibration_runs": ("document", "objective"),
    "initial_plan_previews": ("document", "intent"),
    "customer_billing_offer_bindings": ("profile",),
    "customer_workspace_billing": ("qualification",),
    "outcome_assessments_v3": ("document",),
    "outcome_feedback_records": ("document",),
    "optimization_candidate_jobs": ("work",),
    "optimization_candidate_results": ("decision",),
    "google_original_completions": ("document",),
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
    "initial_budget_mandate_preparations": ("document",),
    "optimization_mandate_preparations": ("document",),
    "provider_execution_revisions": ("policy",),
    "provider_execution_reviews": ("document",),
    "provider_reservation_replacements": ("document",),
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
    ("reported_feedback_jobs", "document"): ReportedAcquisitionRequestV1,
    ("reported_window_capsules", "document"): ReportedWindowCapsuleV1,
    ("reported_action_comparisons", "document"): OperationalReportedComparisonV1,
    ("reported_feedback_slots", "document"): ReportedFeedbackPreviewV1,
    ("initial_observations", "document"): ObservationV1,
    ("initial_calibration_runs", "document"): CalibrationReportV1,
    ("initial_calibration_runs", "objective"): EfficiencyObjectiveV1,
    ("customer_billing_offer_bindings", "profile"): OfferProfileV1,
    ("customer_workspace_billing", "qualification"): OfferQualificationV1,
    ("outcome_assessments_v3", "document"): OwnedV3Assessment,
    ("outcome_feedback_records", "document"): FeedbackContribution,
    ("provider_reservation_replacements", "document"): ReplacementAuditDocument,
    ("action_outcome_assessments", "assessment"): OwnedAssessment,
    ("crm_events", "normalized_payload"): CrmEvent,
    ("customer_goal_revisions", "definition"): GoalDefinition,
    ("spending_mandate_revisions", "definition"): MandateDefinition,
    ("mandate_actions", "draft"): ActionDraft,
    ("customer_campaign_revisions", "artifact"): ReviewArtifact,
    ("publication_plans", "document"): PublishPlan,
    ("provider_reviews", "review"): ProviderPublicationReview,
    ("provider_reviews", "plan"): ProviderPublishPlan,
    ("initial_budget_mandate_preparations", "document"): BudgetMandatePreparationV1,
    ("optimization_mandate_preparations", "document"): OptimizationMandatePreparationV1,
    ("provider_execution_revisions", "policy"): ProviderMandatePolicy,
    ("provider_exposure_reservations", "evidence"): ExposureEvidence,
    ("provider_execution_receipts", "projection"): NormalizedProviderReceipt,
    ("publication_steps", "request"): BoundRequest,
    ("publication_steps", "receipt"): PublishReceipt,
    ("publication_receipts", "request"): BoundRequest,
    ("publication_receipts", "receipt"): PublishReceipt,
}
ADAPTERS: dict[tuple[str, str], TypeAdapter[Any]] = {
    ("google_original_completions", "document"): TypeAdapter(
        Annotated[
            GoogleCompletionDocument | GoogleExecutionCompletionV2,
            Field(discriminator="schema_version"),
        ]
    ),
    ("initial_plan_previews", "document"): TypeAdapter(InitialPreview),
    ("initial_plan_previews", "intent"): TypeAdapter(PreviewIntentV1 | PreviewIntentV2),
    ("commerce_measurement_publications", "manifest"): MANIFEST,
    ("customer_social_configuration_reviews", "document"): TypeAdapter(
        Annotated[
            SocialConfigurationDocument
            | LegacySocialConfigurationDocumentV1
            | LinkedPushConfigurationDocumentV1,
            Field(discriminator="schema_version"),
        ]
    ),
    ("provider_execution_reviews", "document"): TypeAdapter(
        Annotated[
            CreationExecutionReview
            | ActivationExecutionReview
            | OptimizationExecutionReview
            | RepeatOptimizationReview,
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
ADAPTERS[("optimization_candidate_jobs", "work")] = WORK_DOCUMENT_ADAPTER
ADAPTERS[("optimization_candidate_results", "decision")] = DECISION_DOCUMENT_ADAPTER

INTERNAL = {
    "original_session_digest",
    "candidate_provenance_required",
    "automatic_authority_required",
    "auth_session_digest",
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
    ("planning_catalog_receipts", "authenticated_at"),
    *(
        ("commerce_acquisition_jobs", field)
        for field in (
            "native_connection_id",
            "integration_id",
            "actor_id",
            "authenticated_at",
            "identity_digest",
            "request",
            "profile",
            "profile_digest",
            "lease_token",
            "charged_bytes",
        )
    ),
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


def validation_fields(table: str) -> tuple[str, ...]:
    """Internal scalar lineage needed for validation, never added to export fields."""
    if table == "selected_reporting_captures":
        # This is the selected reporting document commitment, not a customer
        # idempotency/session secret. Validate the complete stored row explicitly.
        return ("request_digest",)
    return ("fence", "request_digest") if table == "google_original_completions" else ()


def exclusion(table: str, column: str) -> str:
    if (
        table in PRIVATE_STAGING_TABLES
        or (
            table == "meta_staged_metrics" and column in {"presence_context_token", "presence_json"}
        )
        or column in INTERNAL
        or (table, column) in INTERNAL_TABLE_FIELDS
    ):
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
    if bind_reported_document(table, field, row, document):
        return
    if bind_initial_document(table, field, row, document):
        return

    """Bind added domains to owned scalar lineage, never trust JSON scope alone."""
    if isinstance(document, ManifestBasis):
        bind_manifest(row, document, raw)
    elif isinstance(document, OfferProfileV1):
        bound = BoundOfferV1(
            id=row["id"],
            workspace_id=row["workspace_id"],
            checkout_key=row["checkout_key"],
            profile=document,
            created_at=utc(row["created_at"]),
        )
        if (
            row["profile_digest"] != offer_digest(document)
            or row["binding_digest"] != offer_digest(bound)
            or any(row[key] != value for key, value in document.scope.columns().items())
        ):
            raise ValueError("billing offer row mismatch")
    elif isinstance(document, OfferQualificationV1):
        if (
            row["subscription_offer_binding_id"] != document.binding_id
            or row["qualification_digest"] != offer_digest(document)
            or row["customer_id"] != document.customer_id
            or row["subscription_id"] != document.subscription_id
            or row["price_id"] != document.price_id
            or row["status"] != document.status
            or row["period_end"] is None
            or utc(row["period_end"]) != document.period_end
            or row["verified_at"] is None
            or utc(row["verified_at"]) != document.observed_at
            or any(row[key] != value for key, value in document.scope.columns().items())
        ):
            raise ValueError("billing qualification row mismatch")
    elif isinstance(document, OwnedV3Assessment):
        if (
            document.context.scope.workspace_id != row["workspace_id"]
            or document.context.environment != row["environment"]
            or document.receipt.attempt_id != row["attempt_id"]
            or document.receipt.receipt_id != row["receipt_id"]
            or document.receipt.sequence != row["receipt_sequence"]
            or document.context.scope.store_id != row["store_id"]
            or document.context.scope.generation != row["generation"]
            or document.context.scope.privacy_epoch != row["privacy_epoch"]
            or document.input_digest != row["input_digest"]
            or assessment_digest(document.model_dump(mode="json")) != row["document_digest"]
        ):
            raise ValueError("v3 assessment ownership mismatch")
    elif isinstance(document, FeedbackContribution):
        if (
            document.status != "eligible"
            or document.workspace_id != row["workspace_id"]
            or document.environment != row["environment"]
            or document.original_attempt_id != row["attempt_id"]
            or document.assessment_digest != row["assessment_digest"]
            or document.policy_digest != row["policy_digest"]
            or assessment_digest(document.model_dump(mode="json")) != row["document_digest"]
        ):
            raise ValueError("feedback ownership mismatch")
    elif isinstance(
        document, (CandidateWork, CandidateWorkV2, ReportedRuleWorkV1, InitialReportedRuleWorkV1)
    ):
        if (
            document.scope.account.workspace_id != row["workspace_id"]
            or document.policy.environment != row["environment"]
            or document.scope.source.publication_id != row["publication_id"]
            or document.scope.source.attempt_id != row["attempt_id"]
            or (
                isinstance(
                    document, (CandidateWorkV2, ReportedRuleWorkV1, InitialReportedRuleWorkV1)
                )
                and document.selection.actor_id != row["actor_id"]
            )
            or document.digest() != row["input_digest"]
        ):
            raise ValueError("candidate work ownership mismatch")
    elif isinstance(
        document, (CandidateDecision, ReportedRuleCandidateV1, InitialReportedRuleCandidateV1)
    ):
        if (
            document.scope.account.workspace_id != row["workspace_id"]
            or document.digest() != row["decision_digest"]
            or document.policy_digest != row["policy_digest"]
            or document.evidence_digest != row["evidence_digest"]
        ):
            raise ValueError("candidate result ownership mismatch")
    elif isinstance(
        document,
        (
            SocialConfigurationDocument,
            LegacySocialConfigurationDocumentV1,
            LinkedPushConfigurationDocumentV1,
        ),
    ):
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
        expected: dict[str, Any] = {
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
    elif isinstance(document, OptimizationMandatePreparationV1):
        expected = {
            "workspace_id": document.workspace_id,
            "mandate_id": document.mandate_id,
            "mandate_revision": document.mandate_revision,
            "provider_policy_digest": document.provider_policy_digest,
            "preparation_digest": document.digest(),
        }
        if any(row[key] != value for key, value in expected.items()):
            raise ValueError("optimization origin ownership mismatch")
    elif isinstance(document, BudgetMandatePreparationV1):
        if any(
            row[key] != value
            for key, value in {
                "workspace_id": document.workspace_id,
                "mandate_id": document.mandate_id,
                "mandate_revision": document.mandate_revision,
                "policy_digest": document.policy_digest,
                "digest": document.digest(),
            }.items()
        ):
            raise ValueError("mandate preparation ownership mismatch")
    elif isinstance(document, (GoogleCompletionDocument, GoogleExecutionCompletionV2)):
        capture = document.capture
        expected = {
            "attempt_id": document.attempt_id
            if isinstance(document, GoogleExecutionCompletionV2)
            else document.capture.attempt_id,
            "workspace_id": capture.account.workspace_id,
            "fence": capture.fence,
            "request_digest": capture.request_digest,
            "digest": document.digest(),
        }
        if any(row[key] != value for key, value in expected.items()):
            raise ValueError("original response row ownership mismatch")
    elif isinstance(document, ReplacementAuditDocument):
        expected = {
            "workspace_id": document.snapshot.workspace_id,
            "ledger_id": document.snapshot.ledger_id,
            "environment": document.snapshot.environment,
            "budget_owner_key": document.snapshot.budget_owner_key,
            "predecessor_id": document.predecessor_id,
            "successor_id": document.successor_id,
            "successor_run_id": document.successor_run_id,
            "review_id": document.review_id,
            "old_amount_micros": document.snapshot.ancestry[-1].amount_micros,
            "new_amount_micros": document.evidence.portfolio.proposed_owner_upper_micros,
            "digest": document.digest(),
            "actor": document.actor,
        }
        if any(row[key] != value for key, value in expected.items()):
            raise ValueError("replacement audit row ownership mismatch")
    elif isinstance(document, (OptimizationExecutionReview, RepeatOptimizationReview)):
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


def serialize(
    table: str,
    row: Mapping[str, Any],
    *,
    db: Session | None = None,
    presence_context: PresenceExportContext | None = None,
    selected_context: SelectedExportContext | None = None,
) -> tuple[dict[str, Any], list[str]]:
    from app.campaign_performance.presence_storage import TABLES as PRESENCE_TABLES
    from app.campaign_performance.selected_storage import TABLES as SELECTED_TABLES
    from app.planning_documents.storage import CATALOG_RECEIPT_TABLES, PLANNING_TABLES, export_row

    if table == "google_reporting_range_receipts":
        from app.campaign_performance.range_receipts import export_range_receipt

        if db is None:
            raise ValueError("range receipt export requires owned snapshot")
        return export_range_receipt(
            db, {k: v for k, v in row.items() if k != "_export_oversized"}
        ), []

    if table in SELECTED_TABLES:
        if db is None:
            raise ValueError("selected export requires owned snapshot")
        context_selected = selected_context or SelectedExportContext(db)
        if context_selected.db is not db:
            raise ValueError("selected export session mismatch")
        return context_selected.export(
            table, {key: value for key, value in row.items() if key != "_export_oversized"}
        ), []

    if table in PRESENCE_TABLES:
        if db is None:
            raise ValueError("presence export requires scoped snapshot validation")
        context = presence_context or PresenceExportContext(db)
        if context.db is not db:
            raise ValueError("presence export session mismatch")
        return context.export(table, row), []

    if table in CATALOG_RECEIPT_TABLES:
        from app.planning_documents.catalog_receipt_export import export_receipt_row

        if db is None:
            raise ValueError("receipt export requires scoped database validation")
        return export_receipt_row(db, table, row), []
    if table in PLANNING_TABLES:
        if table == "planning_document_versions":
            from app.planning_documents.documents import PlanVersion
            from app.planning_documents.selected_plan_history import validate_selected_plan_history
            from app.planning_documents.storage import document_for_row

            selected_document = document_for_row(table, row)
            assert isinstance(selected_document, PlanVersion)
            if selected_document.selected_reporting_proof is not None:
                if db is None:
                    raise ValueError("selected plan export requires owned snapshot")
                validate_selected_plan_history(db, selected_document)
        if table == "planning_input_revisions" and db is not None:
            from app.planning_documents.catalog_receipt_export import validate_input_receipt_export

            validate_input_receipt_export(db, row)
        return export_row(table, row), []
    if table == "initial_preview_execution_proofs":
        try:
            return export_execution_proof(row), []
        except (ValueError, TypeError, KeyError, ValidationError):
            return {}, list(fields(table))
    if table == "initial_preview_reviews":
        try:
            return export_review_link(row), []
        except (ValueError, TypeError, KeyError, ValidationError):
            return {}, list(fields(table))
    output, missing = {}, []
    for field in fields(table):
        value = row[field]
        try:
            if field in JSON_FIELDS.get(table, ()) and value is not None:
                if (table, field) in {
                    ("action_outcome_assessments", "assessment"),
                    ("outcome_assessments_v3", "document"),
                    ("outcome_feedback_records", "document"),
                } and len(
                    json.dumps(
                        value, sort_keys=True, separators=(",", ":"), allow_nan=False
                    ).encode()
                ) > 256 * 1024:
                    raise ValueError("assessment exceeds export bound")
                model = TYPED.get((table, field))
                if table in {"intelligence_records", "intelligence_revisions"}:
                    model = PAYLOAD_MODELS[RecordKind(row["kind"])]
                value = bounded_json(value)
                if model is not None:
                    document = model.model_validate(value)
                    bind_document(table, field, row, document, value)
                    value = (
                        value
                        if isinstance(document, ManifestBasis)
                        else document.model_dump(mode="json")
                    )
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
                    if table in {
                        "optimization_candidate_jobs",
                        "optimization_candidate_results",
                    } or (
                        table == "customer_social_configuration_reviews"
                        and isinstance(value, dict)
                        and value.get("schema_version")
                        == "inlet.tiktok-linked-push-configuration-review.v1"
                    ):
                        # Strict JSON schemas decode dates/arrays as JSON; preserve
                        # historical Python validation for other documents.
                        document = adapter.validate_json(json.dumps(value, allow_nan=False))
                    else:
                        document = adapter.validate_python(value)
                    bind_document(table, field, row, document, value)
                    value = (
                        value
                        if isinstance(document, ManifestBasis)
                        else document.model_dump(mode="json")
                    )
                json.dumps(value, allow_nan=False)
            else:
                value = scalar(value)
            output[field] = value
        except (ValueError, TypeError, KeyError, ValidationError):
            missing.append(field)
    return output, missing
