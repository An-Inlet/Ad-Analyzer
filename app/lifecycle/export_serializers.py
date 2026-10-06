"""Customer export v1 domain allowlists. Never serialize arbitrary ORM state."""

import json
import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from app.campaign_review.contracts import ReviewArtifact
from app.crm.schemas import CrmEvent
from app.goals.schemas import GoalDefinition
from app.intelligence.schemas import PAYLOAD_MODELS, RecordKind
from app.lifecycle.inventory import scalar
from app.lifecycle.registry import TABLES
from app.mandates.schemas import ActionDraft, MandateDefinition
from app.publication.contracts import BoundRequest, PublishPlan, PublishReceipt

# Explicit customer-facing structured fields. Free-form fields remain bounded JSON,
# not arbitrary columns or provider transport responses. Typed historical fields use
# their versioned product contracts and reject unknown/invalid persisted documents.
JSON_FIELDS: dict[str, tuple[str, ...]] = {
    "analysis_runs": ("blocking_reasons", "decision_brief", "retry_history"),
    "commerce_snapshots": ("result",),
    "crm_events": ("normalized_payload",),
    "customer_campaign_revisions": ("artifact",),
    "customer_goal_revisions": ("definition",),
    "customer_lifecycle_requests": ("blockers",),
    "execution_audits": ("validation_errors",),
    "intelligence_records": ("data",),
    "intelligence_revisions": ("before_data", "after_data"),
    "lead_attribution": ("attribution_data",),
    "mandate_actions": ("draft",),
    "publication_plans": ("document",),
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
    ("crm_events", "normalized_payload"): CrmEvent,
    ("customer_goal_revisions", "definition"): GoalDefinition,
    ("spending_mandate_revisions", "definition"): MandateDefinition,
    ("mandate_actions", "draft"): ActionDraft,
    ("customer_campaign_revisions", "artifact"): ReviewArtifact,
    ("publication_plans", "document"): PublishPlan,
    ("publication_steps", "request"): BoundRequest,
    ("publication_steps", "receipt"): PublishReceipt,
    ("publication_receipts", "request"): BoundRequest,
    ("publication_receipts", "receipt"): PublishReceipt,
}
# These are deliberately not customer-owned business content. New omissions that
# do not match this explicit set become unsupported omissions, never successful export.
INTERNAL = {
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
INTERNAL_TABLE_FIELDS = {("meta_detail_staged_pages", "payload")}
SECRET_KEY = re.compile(
    r"(?:secret|password|credential|authorization|cookie|session_digest|csrf|"
    r"(?:access|refresh|id)_token|encrypted|private_key)",
    re.I,
)


def fields(table: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (*TABLES[table].fields, *ADDITIONS.get(table, ()), *JSON_FIELDS.get(table, ()))
        )
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


def serialize(table: str, row: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    output, missing = {}, []
    for field in fields(table):
        value = row[field]
        try:
            if field in JSON_FIELDS.get(table, ()) and value is not None:
                model = TYPED.get((table, field))
                if table in {"intelligence_records", "intelligence_revisions"}:
                    model = PAYLOAD_MODELS[RecordKind(row["kind"])]
                value = bounded_json(value)
                if model is not None:
                    value = model.model_validate(value).model_dump(mode="json")
                json.dumps(value, allow_nan=False)
            else:
                value = scalar(value)
            output[field] = value
        except (ValueError, TypeError, KeyError, ValidationError):
            missing.append(field)
    return output, missing
