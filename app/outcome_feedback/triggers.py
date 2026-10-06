"""Owned derived-data erasure; no financial-table writes or external operations."""

from sqlalchemy import DDL, Table, event


def register_triggers(assessment: Table, dependency: Table, feedback: Table, slot: Table) -> None:
    for table in (dependency, assessment, feedback, slot):
        guard = f"inlet_guard_{table.name}"
        body = (
            "IF TG_OP='INSERT' THEN PERFORM id FROM workspaces WHERE id=NEW.workspace_id "
            "FOR UPDATE NOWAIT; ELSIF TG_OP='UPDATE' THEN PERFORM id FROM workspaces "
            "WHERE id IN (OLD.workspace_id, NEW.workspace_id) ORDER BY id FOR UPDATE NOWAIT; "
            "ELSE PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; "
            "END IF; IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;"
        )
        for statement in (
            f"CREATE OR REPLACE FUNCTION {guard}_fn() RETURNS trigger LANGUAGE plpgsql "
            f"AS $$ BEGIN {body} END; $$",
            f"CREATE TRIGGER {guard} BEFORE DELETE OR UPDATE"
            + (" OR INSERT" if table is slot else "")
            + f" ON {table.name} FOR EACH ROW EXECUTE FUNCTION {guard}_fn()",
        ):
            ddl = DDL(statement)  # type: ignore[no-untyped-call]
            event.listen(table, "after_create", ddl.execute_if(dialect="postgresql"))
        body = (
            "DELETE FROM outcome_assessments_v3 WHERE id=OLD.assessment_id "
            "AND workspace_id=OLD.workspace_id;"
            if table is dependency
            else "DELETE FROM optimization_candidate_jobs WHERE workspace_id=OLD.workspace_id; "
            "UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 "
            "WHERE id=OLD.workspace_id;"
        )
        for action in ("DELETE", "UPDATE", "INSERT") if table is slot else ("DELETE", "UPDATE"):
            name = f"inlet_{table.name}_{action.lower()}"
            action_body = body.replace("OLD.", "NEW.") if action == "INSERT" else body
            if action == "UPDATE":
                action_body += body.replace("OLD.", "NEW.")
            prefix = f"CREATE TRIGGER {name} AFTER {action} ON {table.name} FOR EACH ROW "
            statements = (
                ("sqlite", prefix + f"BEGIN {action_body} END"),
                (
                    "postgresql",
                    f"CREATE OR REPLACE FUNCTION {name}_fn() RETURNS trigger "
                    f"LANGUAGE plpgsql AS $$ BEGIN {action_body} RETURN NULL; END; $$",
                ),
                ("postgresql", prefix + f"EXECUTE FUNCTION {name}_fn()"),
            )
            for dialect, statement in statements:
                ddl = DDL(statement)  # type: ignore[no-untyped-call]
                event.listen(table, "after_create", ddl.execute_if(dialect=dialect))
