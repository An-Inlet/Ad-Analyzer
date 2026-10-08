# mypy: disable-error-code=no-untyped-call
# ruff: noqa: E501
"""DDL guards preserve erasable append-only planning history on both databases."""

from sqlalchemy import DDL, Table, event


def statements(name: str, dialect: str) -> tuple[str, ...]:
    trigger = name + "_immutable"
    predicate = None
    if name == "planning_input_revisions":
        predicate = "EXISTS (SELECT 1 FROM customer_goal_previews p WHERE p.id=NEW.confirmed_preview_id AND p.goal_id=NEW.goal_id AND p.revision=NEW.goal_revision)"
    elif name == "planning_document_events":
        predicate = "NEW.prior_sequence IS NULL OR EXISTS (SELECT 1 FROM planning_document_events p WHERE p.workspace_id=NEW.workspace_id AND p.plan_id=NEW.plan_id AND p.sequence=NEW.prior_sequence AND p.version=NEW.version AND p.action_key=NEW.action_key AND p.kind=NEW.kind)"
    extra: tuple[str, ...] = ()
    if predicate is not None:
        if dialect == "sqlite":
            extra = (
                f"CREATE TRIGGER {name}_binding BEFORE INSERT ON {name} WHEN NOT ({predicate}) BEGIN SELECT RAISE(ABORT,'planning binding mismatch'); END",
            )
        else:
            extra = (
                f"CREATE FUNCTION {name}_binding_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NOT ({predicate}) THEN RAISE EXCEPTION 'planning binding mismatch'; END IF; RETURN NEW; END; $$",
                f"CREATE TRIGGER {name}_binding BEFORE INSERT ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_binding_fn()",
            )
    if dialect == "sqlite":
        return extra + (
            f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {name} BEGIN "
            "SELECT RAISE(ABORT,'immutable planning history'); END",
        )
    return extra + (
        f"CREATE FUNCTION {trigger}_fn() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION 'immutable planning history'; END; $$",
        f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {name} FOR EACH ROW "
        f"EXECUTE FUNCTION {trigger}_fn()",
    )


def register(table: Table) -> None:
    for dialect in ("sqlite", "postgresql"):
        for statement in statements(table.name, dialect):
            event.listen(table, "after_create", DDL(statement).execute_if(dialect=dialect))
    event.listen(
        table,
        "after_drop",
        DDL(f"DROP FUNCTION IF EXISTS {table.name}_immutable_fn()").execute_if(
            dialect="postgresql"
        ),
    )

    event.listen(
        table,
        "after_drop",
        DDL(f"DROP FUNCTION IF EXISTS {table.name}_binding_fn()").execute_if(dialect="postgresql"),
    )
