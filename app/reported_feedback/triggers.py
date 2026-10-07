"""Fail-fast workspace fences and complete numeric-graph retraction, never finance."""

from sqlalchemy import DDL, MetaData, event

TABLES = (
    "reported_feedback_jobs",
    "reported_window_capsules",
    "reported_action_comparisons",
    "reported_comparison_dependencies",
    "reported_feedback_slots",
)
JOB_FIXED = (
    "id",
    "workspace_id",
    "account_id",
    "campaign_id",
    "environment",
    "document",
    "document_digest",
    "expires_at",
    "original_attempt_id",
    "original_actor_id",
    "original_session_digest",
    "source_connection_id",
    "source_generation",
    "policy_family",
    "policy_digest",
    "input_digest",
    "opportunity_digest",
    "created_at",
)


def statements(name: str, dialect: str) -> tuple[str, ...]:
    comparison = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"
    changed = " OR ".join(
        f"NEW.{f}{cast} {comparison} OLD.{f}{cast}"
        for f in JOB_FIXED
        for cast in ["::jsonb" if f == "document" and dialect == "postgresql" else ""]
    )
    immutable = changed if name == TABLES[0] else "TRUE"
    live = (
        "julianday(OLD.expires_at) > julianday('now')"
        if dialect == "sqlite"
        else "OLD.expires_at > clock_timestamp()"
    )
    # A slot's aggregate may use ANY workspace comparison, not only its FK parent.
    # Deleting any contributor retracts every potentially dependent numeric output.
    deletion = (
        "DELETE FROM reported_feedback_slots WHERE workspace_id=OLD.workspace_id; "
        if name != "reported_feedback_slots"
        else ""
    )
    if name == "reported_comparison_dependencies":
        deletion += (
            "DELETE FROM reported_action_comparisons WHERE id=OLD.comparison_id "
            "AND workspace_id=OLD.workspace_id;"
        )
    else:
        deletion += (
            "UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 "
            f"WHERE id=OLD.workspace_id AND {live};"
        )
    if dialect == "sqlite":
        return (
            f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} WHEN {immutable} "
            "BEGIN SELECT RAISE(ABORT, 'immutable reported feedback evidence'); END",
            f"CREATE TRIGGER {name}_erase AFTER DELETE ON {name} BEGIN {deletion} END",
        )
    return (
        f"CREATE FUNCTION {name}_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ "
        f"BEGIN IF {immutable} THEN RAISE EXCEPTION 'immutable reported feedback evidence'; "
        "END IF; RETURN NEW; END; $$",
        f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} FOR EACH ROW "
        f"EXECUTE FUNCTION {name}_immutable_fn()",
        f"CREATE FUNCTION {name}_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; "
        "RETURN OLD; END; $$",
        f"CREATE TRIGGER {name}_guard BEFORE DELETE ON {name} FOR EACH ROW "
        f"EXECUTE FUNCTION {name}_guard_fn()",
        f"CREATE FUNCTION {name}_erase_fn() RETURNS trigger LANGUAGE plpgsql AS $$ "
        f"BEGIN {deletion} RETURN NULL; END; $$",
        f"CREATE TRIGGER {name}_erase AFTER DELETE ON {name} FOR EACH ROW "
        f"EXECUTE FUNCTION {name}_erase_fn()",
    )


def register(metadata: MetaData) -> None:
    # Cross-table deletion targets must all exist before installing the graph hooks.
    for name in TABLES:
        for dialect in ("sqlite", "postgresql"):
            for statement in statements(name, dialect):
                event.listen(
                    metadata.tables[TABLES[-1]],
                    "after_create",
                    DDL(statement).execute_if(dialect=dialect),  # type: ignore[no-untyped-call]
                )
