"""Insert binds exact owned preparation; immutable content, erasable planning record."""

from sqlalchemy import DDL, Table, event

NAME = "initial_planning_consents"
MATCH = (
    "EXISTS (SELECT 1 FROM initial_budget_mandate_preparations p "
    "JOIN provider_execution_revisions r ON r.mandate_id=p.mandate_id "
    "AND r.revision=p.mandate_revision AND r.workspace_id=p.workspace_id "
    "WHERE p.mandate_id=NEW.mandate_id AND p.mandate_revision=NEW.mandate_revision "
    "AND p.workspace_id=NEW.workspace_id AND p.policy_digest=NEW.policy_digest "
    "AND p.digest=NEW.preparation_digest AND r.digest=NEW.policy_digest)"
)
SQL = {
    "sqlite": (
        f"CREATE TRIGGER ipc_insert BEFORE INSERT ON {NAME} WHEN NOT {MATCH} "
        "BEGIN SELECT RAISE(ABORT,'planning consent preparation mismatch'); END",
        f"CREATE TRIGGER ipc_update BEFORE UPDATE ON {NAME} "
        "BEGIN SELECT RAISE(ABORT,'immutable planning confirmation'); END",
    ),
    "postgresql": (
        "CREATE FUNCTION ipc_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "IF TG_OP != 'INSERT' THEN RAISE EXCEPTION 'immutable planning confirmation'; END IF; "
        f"IF NOT {MATCH} THEN RAISE EXCEPTION 'planning consent preparation mismatch'; END IF; "
        "RETURN NEW; END; $$",
        f"CREATE TRIGGER ipc_guard BEFORE INSERT OR UPDATE ON {NAME} "
        "FOR EACH ROW EXECUTE FUNCTION ipc_guard_fn()",
    ),
}


def register(table: Table) -> None:
    for dialect, statements in SQL.items():
        for statement in statements:
            event.listen(table, "after_create", DDL(statement).execute_if(dialect=dialect))  # type: ignore[no-untyped-call]
    event.listen(
        table,
        "after_drop",
        DDL("DROP FUNCTION IF EXISTS ipc_guard_fn()").execute_if(dialect="postgresql"),  # type: ignore[no-untyped-call]
    )
