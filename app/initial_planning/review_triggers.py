"""One-way protected origin and immutable link commitments, allowing FK retraction only."""

from sqlalchemy import DDL, Table, event


def statements(dialect: str) -> tuple[str, ...]:
    distinct = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"
    origin = (
        "OLD.initial_preview_origin_id IS NOT NULL AND "
        f"(NEW.initial_preview_origin_id {distinct} OLD.initial_preview_origin_id "
        "OR NOT NEW.initial_preview_provenance_required)"
    )
    fields = [
        "review_id",
        "workspace_id",
        "actor_id",
        "original_session_digest",
        "environment",
        "preview_digest",
        "intent_digest",
        "policy_digest",
        "evidence_digest",
        "native_state_digest",
        "mandate_digest",
        "review_digest",
        "plan_digest",
        "expires_at",
        "created_at",
    ]
    unchanged = " OR ".join(f"NEW.{f} {distinct} OLD.{f}" for f in fields)
    pointer = ["preview_id", "preview_workspace_id", "preview_account_id", "preview_campaign_id"]
    same = " AND ".join(f"NOT (NEW.{f} {distinct} OLD.{f})" for f in pointer)
    null = " AND ".join(f"NEW.{f} IS NULL" for f in pointer)
    changed = f"({unchanged}) OR NOT (({same}) OR ({null}))"
    specs = (
        ("initial_review_origin", "provider_execution_reviews", "UPDATE", origin),
        (
            "initial_review_retained",
            "provider_execution_reviews",
            "DELETE",
            "OLD.initial_preview_provenance_required",
        ),
        ("initial_review_link_immutable", "initial_preview_reviews", "UPDATE", changed),
    )
    result = []
    for name, table, operation, condition in specs:
        if dialect == "sqlite":
            result.append(
                f"CREATE TRIGGER {name} BEFORE {operation} ON {table} WHEN {condition} "
                "BEGIN SELECT RAISE(ABORT, 'immutable initial preview provenance'); END"
            )
        else:
            result.extend(
                (
                    f"CREATE FUNCTION {name}_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                    f"IF {condition} THEN RAISE EXCEPTION 'immutable initial preview provenance'; "
                    f"END IF; RETURN {'OLD' if operation == 'DELETE' else 'NEW'}; END; $$",
                    f"CREATE TRIGGER {name} BEFORE {operation} ON {table} "
                    f"FOR EACH ROW EXECUTE FUNCTION {name}_fn()",
                )
            )
    return tuple(result)


def register(table: Table) -> None:
    # Both target tables exist by the time the link table's after_create fires.
    for dialect in ("sqlite", "postgresql"):
        for sql in statements(dialect):
            event.listen(table, "after_create", DDL(sql).execute_if(dialect=dialect))  # type: ignore[no-untyped-call]
