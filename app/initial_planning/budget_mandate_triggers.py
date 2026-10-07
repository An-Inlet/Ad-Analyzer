"""Immutable authority provenance and exact revision policy binding."""

from sqlalchemy import DDL, Table, event

NAME = "initial_budget_mandate_preparations"
MATCH = (
    "EXISTS (SELECT 1 FROM provider_execution_revisions r WHERE "
    "r.mandate_id=NEW.mandate_id AND r.revision=NEW.mandate_revision "
    "AND r.workspace_id=NEW.workspace_id AND r.digest=NEW.policy_digest)"
)
SQL = {
    "sqlite": (
        f"CREATE TRIGGER ibmp_insert BEFORE INSERT ON {NAME} WHEN NOT {MATCH} "
        "BEGIN SELECT RAISE(ABORT,'mandate preparation policy mismatch'); END",
        *(
            f"CREATE TRIGGER ibmp_{op.lower()} BEFORE {op} ON {NAME} "
            "BEGIN SELECT RAISE(ABORT,'immutable mandate preparation'); END"
            for op in ("UPDATE", "DELETE")
        ),
    ),
    "postgresql": (
        "CREATE FUNCTION ibmp_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "IF TG_OP != 'INSERT' THEN RAISE EXCEPTION 'immutable mandate preparation'; END IF; "
        f"IF NOT {MATCH} THEN RAISE EXCEPTION 'mandate preparation policy mismatch'; END IF; "
        "RETURN NEW; END; $$",
        f"CREATE TRIGGER ibmp_guard BEFORE INSERT OR UPDATE OR DELETE ON {NAME} "
        "FOR EACH ROW EXECUTE FUNCTION ibmp_guard_fn()",
    ),
}


def register(table: Table) -> None:
    for dialect, statements in SQL.items():
        for statement in statements:
            event.listen(table, "after_create", DDL(statement).execute_if(dialect=dialect))  # type: ignore[no-untyped-call]
    event.listen(
        table,
        "after_drop",
        DDL("DROP FUNCTION IF EXISTS ibmp_guard_fn()").execute_if(dialect="postgresql"),  # type: ignore[no-untyped-call]
    )
