"""Fence store, alias and privacy identity writers without changing retention."""

from alembic import op

revision = "20261012_0094"
down_revision = "20261012_0093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for sql in SQL:
            op.execute(sql)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in reversed(TABLES):
            op.execute(f"DROP TRIGGER {table}_workspace_guard ON {table}")
            op.execute(f"DROP FUNCTION {table}_workspace_guard_fn()")


TABLES = ("commerce_stores", "commerce_shop_aliases", "shopify_privacy_identities")
SQL = (
    (
        "\n    CREATE FUNCTION commerce_stores_workspace_guard_fn() RE"
        "TURNS trigger LANGUAGE plpgsql AS $$\n    DECLARE owners inte"
        "ger[] := ARRAY[]::integer[]; owner integer;\n    BEGIN\n      "
        "  \n        IF TG_OP <> 'INSERT' THEN owners := array_append("
        "owners, OLD.workspace_id); END IF;\n        IF TG_OP <> 'DELE"
        "TE' THEN owners := array_append(owners, NEW.workspace_id); E"
        "ND IF;\n        \n        FOR owner IN SELECT DISTINCT x FROM "
        "unnest(owners) x ORDER BY x\n        LOOP\n            PERFORM"
        " id FROM workspaces WHERE id = owner FOR NO KEY UPDATE NOWAI"
        "T;\n            IF NOT FOUND AND TG_OP <> 'DELETE' THEN\n     "
        "           RAISE EXCEPTION 'commerce mutation workspace unav"
        "ailable';\n            END IF;\n            -- A missing owner"
        " is permitted only for DELETE beneath the enforced\n         "
        "   -- workspace CASCADE. Nondeferrable FKs exclude stored or"
        "phan owners;\n            -- the parent deletion itself holds"
        " the workspace row lock.\n        END LOOP;\n        \n        "
        "IF TG_OP = 'DELETE' THEN\n            DELETE FROM commerce_sh"
        "op_aliases WHERE store_id = OLD.id;\n        END IF;\n        "
        "\n        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;\n      "
        "  RETURN NEW;\n    END; $$\n    "
    ),
    (
        "CREATE TRIGGER commerce_stores_workspace_guard BEFORE INSERT"
        " OR UPDATE OR DELETE ON commerce_stores FOR EACH ROW EXECUTE"
        " FUNCTION commerce_stores_workspace_guard_fn()"
    ),
    (
        "\n    CREATE FUNCTION commerce_shop_aliases_workspace_guard_f"
        "n() RETURNS trigger LANGUAGE plpgsql AS $$\n    DECLARE owner"
        "s integer[] := ARRAY[]::integer[]; owner integer; parents te"
        "xt[] := ARRAY[]::text[]; parent record; resolved integer := "
        "0;\n    BEGIN\n        \n        IF TG_OP <> 'INSERT' THEN pare"
        "nts := array_append(parents, OLD.store_id); END IF;\n        "
        "IF TG_OP <> 'DELETE' THEN parents := array_append(parents, N"
        "EW.store_id); END IF;\n        SELECT array_agg(DISTINCT p OR"
        "DER BY p) INTO parents FROM unnest(parents) p;\n        FOR p"
        "arent IN SELECT id, workspace_id FROM commerce_stores\n      "
        "      WHERE id = ANY(parents) ORDER BY id FOR KEY SHARE NOWA"
        "IT\n        LOOP\n            owners := array_append(owners, p"
        "arent.workspace_id);\n            resolved := resolved + 1;\n "
        "       END LOOP;\n        IF resolved <> cardinality(parents)"
        " THEN\n            RAISE EXCEPTION 'commerce alias parent una"
        "vailable';\n        END IF;\n        \n        FOR owner IN SEL"
        "ECT DISTINCT x FROM unnest(owners) x ORDER BY x\n        LOOP"
        "\n            PERFORM id FROM workspaces WHERE id = owner FOR"
        " NO KEY UPDATE NOWAIT;\n            IF NOT FOUND AND TG_OP <>"
        " 'DELETE' THEN\n                RAISE EXCEPTION 'commerce mut"
        "ation workspace unavailable';\n            END IF;\n          "
        "  -- A missing owner is permitted only for DELETE beneath th"
        "e enforced\n            -- workspace CASCADE. Nondeferrable F"
        "Ks exclude stored orphan owners;\n            -- the parent d"
        "eletion itself holds the workspace row lock.\n        END LOO"
        "P;\n        \n        IF TG_OP = 'DELETE' THEN RETURN OLD; END"
        " IF;\n        RETURN NEW;\n    END; $$\n    "
    ),
    (
        "CREATE TRIGGER commerce_shop_aliases_workspace_guard BEFORE "
        "INSERT OR UPDATE OR DELETE ON commerce_shop_aliases FOR EACH"
        " ROW EXECUTE FUNCTION commerce_shop_aliases_workspace_guard_"
        "fn()"
    ),
    (
        "\n    CREATE FUNCTION shopify_privacy_identities_workspace_gu"
        "ard_fn() RETURNS trigger LANGUAGE plpgsql AS $$\n    DECLARE "
        "owners integer[] := ARRAY[]::integer[]; owner integer;\n    B"
        "EGIN\n        \n        IF TG_OP <> 'INSERT' THEN owners := ar"
        "ray_append(owners, OLD.workspace_id); END IF;\n        IF TG_"
        "OP <> 'DELETE' THEN owners := array_append(owners, NEW.works"
        "pace_id); END IF;\n        \n        FOR owner IN SELECT DISTI"
        "NCT x FROM unnest(owners) x ORDER BY x\n        LOOP\n        "
        "    PERFORM id FROM workspaces WHERE id = owner FOR NO KEY U"
        "PDATE NOWAIT;\n            IF NOT FOUND AND TG_OP <> 'DELETE'"
        " THEN\n                RAISE EXCEPTION 'commerce mutation wor"
        "kspace unavailable';\n            END IF;\n            -- A mi"
        "ssing owner is permitted only for DELETE beneath the enforce"
        "d\n            -- workspace CASCADE. Nondeferrable FKs exclud"
        "e stored orphan owners;\n            -- the parent deletion i"
        "tself holds the workspace row lock.\n        END LOOP;\n      "
        "  \n        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;\n    "
        "    RETURN NEW;\n    END; $$\n    "
    ),
    (
        "CREATE TRIGGER shopify_privacy_identities_workspace_guard BE"
        "FORE INSERT OR UPDATE OR DELETE ON shopify_privacy_identitie"
        "s FOR EACH ROW EXECUTE FUNCTION shopify_privacy_identities_w"
        "orkspace_guard_fn()"
    ),
)
