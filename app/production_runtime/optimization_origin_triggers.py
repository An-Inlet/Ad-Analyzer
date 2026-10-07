"""No-rebuild one-to-one origin binding and narrow marked authority immutability."""

from sqlalchemy import DDL, Table, event

TABLE = "optimization_mandate_preparations"
MATCH = (
    "EXISTS (SELECT 1 FROM provider_execution_revisions r WHERE "
    "r.mandate_id=NEW.mandate_id AND r.revision=NEW.mandate_revision "
    "AND r.workspace_id=NEW.workspace_id AND r.digest=NEW.provider_policy_digest "
    "AND r.origin_kind='optimization_customer_v1' "
    "AND r.origin_preparation_digest=NEW.preparation_digest)"
)
BORROW = (
    f"EXISTS (SELECT 1 FROM {TABLE} p WHERE "
    "p.preparation_digest=NEW.origin_preparation_digest AND "
    "(p.mandate_id!=NEW.mandate_id OR p.mandate_revision!=NEW.revision "
    "OR p.workspace_id!=NEW.workspace_id OR p.provider_policy_digest!=NEW.digest))"
)
SIDECAR_SQL = {
    "sqlite": (
        f"CREATE TRIGGER omp_insert BEFORE INSERT ON {TABLE} WHEN NOT {MATCH} "
        "BEGIN SELECT RAISE(ABORT,'optimization origin mismatch'); END",
        *(
            f"CREATE TRIGGER omp_{op.lower()} BEFORE {op} ON {TABLE} "
            "BEGIN SELECT RAISE(ABORT,'immutable optimization origin'); END"
            for op in ("UPDATE", "DELETE")
        ),
    ),
    "postgresql": (
        "CREATE FUNCTION omp_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "IF TG_OP != 'INSERT' THEN RAISE EXCEPTION 'immutable optimization origin'; END IF; "
        f"IF NOT {MATCH} THEN RAISE EXCEPTION 'optimization origin mismatch'; END IF; "
        "RETURN NEW; END; $$",
        f"CREATE TRIGGER omp_guard BEFORE INSERT OR UPDATE OR DELETE ON {TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION omp_guard_fn()",
    ),
}
PARENT_SQL = {
    "sqlite": (
        "CREATE TRIGGER omr_insert BEFORE INSERT ON provider_execution_revisions "
        "WHEN NEW.origin_kind='optimization_customer_v1' AND "
        "((SELECT foreign_keys FROM pragma_foreign_keys)!=1 OR NOT EXISTS ("
        "SELECT 1 FROM pragma_foreign_key_list('provider_execution_revisions') f "
        "WHERE f.\"table\"='optimization_mandate_preparations' "
        "AND f.\"from\"='origin_preparation_digest' AND f.\"to\"='preparation_digest' "
        "AND f.seq=0 AND (SELECT count(*) FROM "
        "pragma_foreign_key_list('provider_execution_revisions') other "
        "WHERE other.id=f.id)=1) "
        f"OR {BORROW}) "
        "BEGIN SELECT RAISE(ABORT,'optimization origin requires enforced exact foreign key'); END",
        "CREATE TRIGGER omr_update BEFORE UPDATE ON provider_execution_revisions "
        "WHEN OLD.origin_kind!='legacy' OR NEW.origin_kind!=OLD.origin_kind "
        "OR NEW.origin_preparation_digest IS NOT OLD.origin_preparation_digest "
        "BEGIN SELECT RAISE(ABORT,'immutable optimization revision origin'); END",
        "CREATE TRIGGER omr_delete BEFORE DELETE ON provider_execution_revisions "
        "WHEN OLD.origin_kind!='legacy' "
        "BEGIN SELECT RAISE(ABORT,'immutable optimization revision origin'); END",
    ),
    "postgresql": (
        "CREATE FUNCTION omr_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "IF TG_OP='INSERT' THEN "
        f"IF NEW.origin_kind='optimization_customer_v1' AND {BORROW} THEN "
        "RAISE EXCEPTION 'optimization origin mismatch'; END IF; RETURN NEW; "
        "ELSIF TG_OP='UPDATE' THEN IF OLD.origin_kind!='legacy' OR "
        "NEW.origin_kind IS DISTINCT FROM OLD.origin_kind OR "
        "NEW.origin_preparation_digest IS DISTINCT FROM OLD.origin_preparation_digest THEN "
        "RAISE EXCEPTION 'immutable optimization revision origin'; END IF; RETURN NEW; "
        "ELSE IF OLD.origin_kind!='legacy' THEN "
        "RAISE EXCEPTION 'immutable optimization revision origin'; END IF; RETURN OLD; "
        "END IF; END; $$",
        "CREATE TRIGGER omr_guard BEFORE INSERT OR UPDATE OR DELETE ON "
        "provider_execution_revisions FOR EACH ROW EXECUTE FUNCTION omr_guard_fn()",
    ),
}


def register(table: Table, *, parent: bool = False) -> None:
    sql = PARENT_SQL if parent else SIDECAR_SQL
    for dialect, statements in sql.items():
        for statement in statements:
            event.listen(table, "after_create", DDL(statement).execute_if(dialect=dialect))  # type: ignore[no-untyped-call]
    name = "omr_guard_fn" if parent else "omp_guard_fn"
    event.listen(
        table,
        "after_drop",
        DDL(f"DROP FUNCTION IF EXISTS {name}()").execute_if(dialect="postgresql"),  # type: ignore[no-untyped-call]
    )
