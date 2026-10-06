# ruff: noqa: E501
"""Derived graph deletion fences; never financial authority or semantic privacy hooks."""

from sqlalchemy import DDL, Table, event


def statements(name: str, dialect: str) -> tuple[str, ...]:
    if name == "initial_calibration_dependencies":
        deletion = "DELETE FROM initial_calibration_runs WHERE id=OLD.calibration_id AND workspace_id=OLD.workspace_id;"
    else:
        live = (
            "julianday(OLD.expires_at) > julianday('now')"
            if dialect == "sqlite"
            else "OLD.expires_at > clock_timestamp()"
        )
        deletion = (
            "UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 "
            f"WHERE id=OLD.workspace_id AND {live};"
        )
    if dialect == "sqlite":
        return (
            f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} BEGIN SELECT RAISE(ABORT, 'immutable initial planning evidence'); END",
            f"CREATE TRIGGER {name}_erase AFTER DELETE ON {name} BEGIN {deletion} END",
        )
    return (
        f"CREATE FUNCTION {name}_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable initial planning evidence'; END; $$",
        f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_immutable_fn()",
        f"CREATE FUNCTION {name}_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; RETURN OLD; END; $$",
        f"CREATE TRIGGER {name}_guard BEFORE DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_guard_fn()",
        f"CREATE FUNCTION {name}_erase_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {deletion} RETURN NULL; END; $$",
        f"CREATE TRIGGER {name}_erase AFTER DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_erase_fn()",
    )


def register(table: Table) -> None:
    for dialect in ("sqlite", "postgresql"):
        for sql in statements(table.name, dialect):
            event.listen(table, "after_create", DDL(sql).execute_if(dialect=dialect))  # type: ignore[no-untyped-call]
