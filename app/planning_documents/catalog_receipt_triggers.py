# mypy: disable-error-code=no-untyped-call
# ruff: noqa: E501
"""Scoped insert bindings and immutable updates; legitimate DELETE remains available."""

from sqlalchemy import DDL, Table, event


def statements(name: str, dialect: str) -> tuple[str, ...]:
    predicate = None
    if name == "planning_catalog_receipts":
        length = (
            "length(CAST(NEW.canonical_json AS BLOB))"
            if dialect == "sqlite"
            else "octet_length(NEW.canonical_json)"
        )
        predicate = (
            "EXISTS (SELECT 1 FROM customer_sessions s JOIN customer_memberships m "
            "ON m.user_id=s.user_id WHERE s.digest=NEW.session_digest "
            "AND s.user_id=NEW.actor_id AND s.authenticated_at=NEW.authenticated_at "
            "AND m.workspace_id=NEW.workspace_id AND m.role='owner' AND m.status='active') "
            f"AND NEW.payload_bytes={length}"
        )
    elif name == "planning_input_catalog_receipts":
        predicate = (
            "EXISTS (SELECT 1 FROM planning_input_revisions i "
            "JOIN planning_catalog_receipts r ON r.workspace_id=i.workspace_id "
            "WHERE i.workspace_id=NEW.workspace_id AND i.plan_id=NEW.plan_id "
            "AND i.revision=NEW.input_revision AND r.id=NEW.receipt_id "
            "AND r.account_id=NEW.account_id AND r.connection_id=NEW.connection_id "
            "AND i.digest=NEW.input_digest AND i.actor_id=r.actor_id "
            "AND r.composite_digest=NEW.composite_digest "
            "AND NEW.created_at>=i.created_at AND NEW.created_at<r.expires_at)"
        )
    binding: tuple[str, ...] = ()
    if predicate is not None:
        if dialect == "sqlite":
            binding = (
                f"CREATE TRIGGER {name}_binding BEFORE INSERT ON {name} WHEN NOT ({predicate}) BEGIN SELECT RAISE(ABORT,'catalog receipt binding mismatch'); END",
            )
        else:
            binding = (
                f"CREATE FUNCTION {name}_binding_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NOT ({predicate}) THEN RAISE EXCEPTION 'catalog receipt binding mismatch'; END IF; RETURN NEW; END; $$",
                f"CREATE TRIGGER {name}_binding BEFORE INSERT ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_binding_fn()",
            )
    if dialect == "sqlite":
        return binding + (
            f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} BEGIN SELECT RAISE(ABORT,'immutable catalog receipt'); END",
        )
    return binding + (
        f"CREATE FUNCTION {name}_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable catalog receipt'; END; $$",
        f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_immutable_fn()",
    )


def register(table: Table) -> None:
    for dialect in ("sqlite", "postgresql"):
        for statement in statements(table.name, dialect):
            event.listen(table, "after_create", DDL(statement).execute_if(dialect=dialect))
    for kind in ("immutable", "binding"):
        event.listen(
            table,
            "after_drop",
            DDL(f"DROP FUNCTION IF EXISTS {table.name}_{kind}_fn()").execute_if(
                dialect="postgresql"
            ),
        )
