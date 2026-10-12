# mypy: disable-error-code=no-untyped-call
"""Workspace mutation fences for store/domain/erasure-identity membership.

PostgreSQL fails fast because row triggers may already hold child row locks.
SQLite writers already reserve the database; readers still need BEGIN IMMEDIATE.
No erasure, retention, privacy revision or source-currentness policy is added.
"""

from sqlalchemy import DDL, Table, event

TABLES = ("commerce_stores", "commerce_shop_aliases", "shopify_privacy_identities")


def statements(table: str) -> tuple[str, ...]:
    if table not in TABLES:
        raise ValueError("unsupported commerce mutation fence")
    alias = table == "commerce_shop_aliases"
    declarations = "owners integer[] := ARRAY[]::integer[]; owner integer;"
    if alias:
        declarations += " parents text[] := ARRAY[]::text[]; parent record; resolved integer := 0;"
        resolve = """
        IF TG_OP <> 'INSERT' THEN parents := array_append(parents, OLD.store_id); END IF;
        IF TG_OP <> 'DELETE' THEN parents := array_append(parents, NEW.store_id); END IF;
        SELECT array_agg(DISTINCT p ORDER BY p) INTO parents FROM unnest(parents) p;
        FOR parent IN SELECT id, workspace_id FROM commerce_stores
            WHERE id = ANY(parents) ORDER BY id FOR KEY SHARE NOWAIT
        LOOP
            owners := array_append(owners, parent.workspace_id);
            resolved := resolved + 1;
        END LOOP;
        IF resolved <> cardinality(parents) THEN
            RAISE EXCEPTION 'commerce alias parent unavailable';
        END IF;
        """
    else:
        resolve = """
        IF TG_OP <> 'INSERT' THEN owners := array_append(owners, OLD.workspace_id); END IF;
        IF TG_OP <> 'DELETE' THEN owners := array_append(owners, NEW.workspace_id); END IF;
        """
    cleanup = ""
    if table == "commerce_stores":
        # Alias ownership must remain resolvable. Remove exactly the aliases which
        # the existing CASCADE would remove, while this guarded parent is visible.
        cleanup = """
        IF TG_OP = 'DELETE' THEN
            DELETE FROM commerce_shop_aliases WHERE store_id = OLD.id;
        END IF;
        """
    body = f"""
    CREATE FUNCTION {table}_workspace_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE {declarations}
    BEGIN
        {resolve}
        FOR owner IN SELECT DISTINCT x FROM unnest(owners) x ORDER BY x
        LOOP
            PERFORM id FROM workspaces WHERE id = owner FOR NO KEY UPDATE NOWAIT;
            IF NOT FOUND AND TG_OP <> 'DELETE' THEN
                RAISE EXCEPTION 'commerce mutation workspace unavailable';
            END IF;
            -- A missing owner is permitted only for DELETE beneath the enforced
            -- workspace CASCADE. Nondeferrable FKs exclude stored orphan owners;
            -- the parent deletion itself holds the workspace row lock.
        END LOOP;
        {cleanup}
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END; $$
    """
    return (
        body,
        f"CREATE TRIGGER {table}_workspace_guard BEFORE INSERT OR UPDATE OR DELETE "
        f"ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_workspace_guard_fn()",
    )


def register(table: Table) -> None:
    for sql in statements(table.name):
        event.listen(table, "after_create", DDL(sql).execute_if(dialect="postgresql"))
    event.listen(
        table,
        "after_drop",
        DDL(f"DROP FUNCTION IF EXISTS {table.name}_workspace_guard_fn()").execute_if(
            dialect="postgresql"
        ),
    )
