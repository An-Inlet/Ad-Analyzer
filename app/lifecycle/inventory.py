"""Scoped counts and scalar-only export projection; never query unowned global rows."""

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.database.session import Base
from app.lifecycle.contracts import LifecycleBlockerV1, LifecycleScopeV1
from app.lifecycle.registry import TABLES

MAX_SECTION_BYTES = 4 * 1024 * 1024
MAX_ROW_BYTES = 64 * 1024


def verify_registry() -> None:
    if set(Base.metadata.tables) != set(TABLES):
        raise ValueError("lifecycle table classification incomplete")
    for name, policy in TABLES.items():
        if not set(policy.fields).issubset(Base.metadata.tables[name].c.keys()):
            raise ValueError("lifecycle field classification invalid")


def predicate(name: str, scope: LifecycleScopeV1) -> ColumnElement[bool]:
    policy, table = TABLES[name], Base.metadata.tables[name]
    if policy.scope == "root":
        return table.c.id == scope.workspace_id
    if policy.scope == "workspace":
        return table.c.workspace_id == scope.workspace_id
    if policy.scope == "usage_policy":
        return table.c.scope == f"workspace:{scope.workspace_id}"
    if name == "ads":
        # Search/social child graphs have distinct nullable parent columns.
        return or_(
            table.c.ad_group_id.in_(
                select(Base.metadata.tables["ad_groups"].c.id).where(predicate("ad_groups", scope))
            ),
            table.c.ad_set_id.in_(
                select(Base.metadata.tables["ad_sets"].c.id).where(predicate("ad_sets", scope))
            ),
        )
    if name == "customer_billing_events":
        billing = Base.metadata.tables["customer_workspace_billing"]
        return (
            select(billing.c.workspace_id)
            .where(
                billing.c.workspace_id == scope.workspace_id,
                billing.c.customer_id == table.c.customer_id,
                billing.c.provider == table.c.provider,
                billing.c.environment == table.c.environment,
                billing.c.merchant_account_id == table.c.merchant_account_id,
            )
            .exists()
        )
    if policy.parent is not None:
        local, parent, remote = policy.parent
        parent_table = Base.metadata.tables[parent]
        return table.c[local].in_(select(parent_table.c[remote]).where(predicate(parent, scope)))
    raise ValueError("table has no proven workspace ownership")


def inventory(db: Session, scope: LifecycleScopeV1) -> dict[str, Any]:
    verify_registry()
    sections: list[dict[str, Any]] = []
    for name, policy in TABLES.items():
        table = Base.metadata.tables[name]
        unscoped = policy.scope in {"identity_global", "platform_global", "unclassified"}
        count = (
            None
            if unscoped
            else db.scalar(select(func.count()).select_from(table).where(predicate(name, scope)))
        )
        sections.append(
            {
                "table": name,
                "scope": policy.scope,
                "count": count,
                "protected": policy.protected,
                "export_fields": list(policy.fields),
                "omitted_fields": sorted(set(table.c.keys()) - set(policy.fields)),
            }
        )
    return {
        "schema_version": "inlet.lifecycle.inventory.v1",
        "scope": scope.model_dump(),
        "sections": sections,
        "disposition_policy": None,
        "media_archive_complete": False,
        "closure_complete": False,
        "blockers": blockers(db, scope),
    }


def blockers(db: Session, scope: LifecycleScopeV1) -> list[dict[str, Any]]:
    result = [
        LifecycleBlockerV1(
            code="retention_policy_unset", subsystem="lifecycle", resolution_kind="owner_policy"
        ).model_dump(),
        LifecycleBlockerV1(
            code="legacy_scope_unclassified",
            subsystem="inventory",
            resolution_kind="implementation",
        ).model_dump(),
    ]
    for name, states in {
        "mandate_actions": ["dispatching", "outcome_unknown"],
        "publication_steps": ["dispatching", "unknown", "conflict"],
        "provider_execution_steps": ["dispatching", "emitting", "unknown", "conflict"],
        "provider_exposure_reservations": ["held"],
    }.items():
        table = Base.metadata.tables[name]
        if db.scalar(
            select(table.c.state).where(predicate(name, scope), table.c.state.in_(states)).limit(1)
        ):
            result.append(
                LifecycleBlockerV1(
                    code="publication_unresolved",
                    subsystem=name,
                    resolution_kind="operator_evidence",
                ).model_dump()
            )
    return result


def scalar(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise ValueError("export value is not an allowlisted scalar")


def export_section(
    db: Session, scope: LifecycleScopeV1, name: str, *, limit: int = 1000
) -> dict[str, Any]:
    """Bounded internal serializer, not a complete archive or snapshot download endpoint."""
    verify_registry()
    if type(limit) is not int or not 1 <= limit <= 1000 or name not in TABLES:
        raise ValueError("invalid export section request")
    policy, table = TABLES[name], Base.metadata.tables[name]
    if not policy.fields:
        raise ValueError("section is not workspace-exportable")
    fields = [table.c[field] for field in policy.fields]
    rows: list[dict[str, Any]] = []
    measured, truncated = 0, False
    result = db.execute(
        select(*fields)
        .where(predicate(name, scope))
        .order_by(*table.primary_key.columns)
        .limit(limit + 1)
        .execution_options(yield_per=1)
    ).mappings()
    try:
        for row in result:
            from app.planning_documents.storage import (
                CATALOG_RECEIPT_TABLES,
                MAX_PLANNING_ROW_BYTES,
                PLANNING_TABLES,
                export_row,
            )

            if name in CATALOG_RECEIPT_TABLES:
                from app.planning_documents.catalog_receipt_export import export_receipt_row

                projected = export_receipt_row(db, name, dict(row))
            else:
                if name == "planning_input_revisions":
                    from app.planning_documents.catalog_receipt_export import (
                        validate_input_receipt_export,
                    )

                    validate_input_receipt_export(db, dict(row))
                projected = (
                    export_row(name, dict(row))
                    if name in PLANNING_TABLES
                    else {key: scalar(value) for key, value in row.items()}
                )
            row_limit = MAX_PLANNING_ROW_BYTES if name in PLANNING_TABLES else MAX_ROW_BYTES
            size = len(json.dumps(projected, allow_nan=False).encode())
            if size > row_limit:
                raise ValueError("export row exceeds bound")
            if len(rows) == limit or measured + size > MAX_SECTION_BYTES:
                truncated = True
                break
            rows.append(projected)
            measured += size
    finally:
        result.close()
    return {
        "schema_version": "inlet.lifecycle.section.v1",
        "table": name,
        "scope": scope.model_dump(),
        "rows": rows,
        "truncated": truncated,
        "complete_export": False,
        "omitted_fields": sorted(set(table.c.keys()) - set(policy.fields)),
        "media_archive_complete": False,
    }
