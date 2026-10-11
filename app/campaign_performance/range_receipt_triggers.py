# ruff: noqa: E501
# mypy: disable-error-code=no-untyped-call
"""Receipt metadata binding and transactional raw-erasure privacy fence; frozen0092."""

from sqlalchemy import DDL, Table, event

TABLE = "google_reporting_range_receipts"


def binding(dialect: str) -> str:
    def value(path: str) -> str:
        if dialect == "sqlite":
            return f"json_extract(NEW.canonical_json,'$.{path}')"
        return "(NEW.canonical_json::jsonb #>> '{" + path.replace(".", ",") + "}')"

    checks = [
        f"{value('schema_version')}='inlet.google-reporting-range-receipt.v1'",
        f"{value('final_scope.platform')}='google_ads'",
        f"{value('original_scope.platform')}='google_ads'",
        f"{value('query_version')}='google.v24.campaign-day.metrics-conversions.v1'",
    ]
    for col, path in {
        "request_id": "request_id",
        "workspace_id": "final_scope.workspace_id",
        "account_id": "final_scope.account_id",
        "connection_id": "final_scope.connection_id",
        "completion_id": "completion_id",
        "job_id": "job_id",
        "initiating_customer_id": "initiating_customer_id",
    }.items():
        checks.append(f"CAST(NEW.{col} AS TEXT)=CAST({value(path)} AS TEXT)")
    for name in (
        "workspace_id",
        "account_id",
        "connection_id",
        "platform",
        "source_connection_ref",
        "generation",
        "native_account_id",
        "currency",
        "time_zone",
    ):
        checks.append(
            f"CAST({value('original_scope.' + name)} AS TEXT)=CAST({value('final_scope.' + name)} AS TEXT)"
        )
    checks.append(
        f"CAST({value('original_scope.privacy_revision')} AS BIGINT)<=CAST({value('final_scope.privacy_revision')} AS BIGINT)"
    )
    checks.append(
        "EXISTS(SELECT 1 FROM job_runs j WHERE j.id=NEW.job_id AND j.workspace_id=NEW.workspace_id AND j.account_id=NEW.account_id AND j.connection_id=NEW.connection_id AND CAST(j.platform AS TEXT)='google_ads' AND CAST(j.status AS TEXT)='succeeded' AND j.job_name='google_customer_range_read')"
    )
    completion = [
        "c.id=NEW.completion_id",
        "c.account_id=NEW.account_id",
        "c.workspace_id=NEW.workspace_id",
        "c.platform='google_ads'",
    ]
    for col, path in {
        "source_connection_ref": "final_scope.source_connection_ref",
        "generation": "final_scope.generation",
        "privacy_revision": "final_scope.privacy_revision",
        "currency": "final_scope.currency",
        "time_zone": "final_scope.time_zone",
        "manifest_digest": "manifest_digest",
        "query_version": "query_version",
        "row_count": "row_count",
        "starts_on": "requested_starts_on",
        "ends_on": "requested_ends_on",
    }.items():
        completion.append(f"CAST(c.{col} AS TEXT)=CAST({value(path)} AS TEXT)")
    completion.append(
        f"julianday(c.completed_at)=julianday({value('completed_at')})"
        if dialect == "sqlite"
        else f"c.completed_at=CAST({value('completed_at')} AS TIMESTAMP WITH TIME ZONE)"
    )
    checks.append(
        "EXISTS(SELECT 1 FROM campaign_performance_completions c WHERE "
        + " AND ".join(completion)
        + ")"
    )
    checks.append(
        "NEW.payload_bytes="
        + (
            "length(CAST(NEW.canonical_json AS BLOB))"
            if dialect == "sqlite"
            else "octet_length(NEW.canonical_json)"
        )
    )
    if dialect == "sqlite":
        checks.append("(SELECT foreign_keys FROM pragma_foreign_keys)=1")
    return " AND ".join(checks)


def statements(dialect: str) -> tuple[str, ...]:
    predicate = binding(dialect)
    erase = "DELETE FROM initial_calibration_runs WHERE workspace_id=OLD.workspace_id AND account_id=OLD.account_id; UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id;"
    if dialect == "sqlite":
        return (
            f"CREATE TRIGGER grr_binding BEFORE INSERT ON {TABLE} WHEN NOT COALESCE(({predicate}),0) BEGIN SELECT RAISE(ABORT,'range receipt binding unavailable'); END",
            f"CREATE TRIGGER grr_immutable BEFORE UPDATE ON {TABLE} BEGIN SELECT RAISE(ABORT,'immutable range receipt'); END",
            f"CREATE TRIGGER grr_erase AFTER DELETE ON {TABLE} BEGIN {erase} END",
        )
    return (
        f"CREATE FUNCTION grr_binding_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NOT COALESCE(({predicate}),false) THEN RAISE EXCEPTION 'range receipt binding unavailable'; END IF; RETURN NEW; END; $$",
        f"CREATE TRIGGER grr_binding BEFORE INSERT ON {TABLE} FOR EACH ROW EXECUTE FUNCTION grr_binding_fn()",
        "CREATE FUNCTION grr_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable range receipt'; END; $$",
        f"CREATE TRIGGER grr_immutable BEFORE UPDATE ON {TABLE} FOR EACH ROW EXECUTE FUNCTION grr_immutable_fn()",
        "CREATE FUNCTION grr_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; RETURN OLD; END; $$",
        f"CREATE TRIGGER grr_guard BEFORE DELETE ON {TABLE} FOR EACH ROW EXECUTE FUNCTION grr_guard_fn()",
        f"CREATE FUNCTION grr_erase_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {erase} RETURN NULL; END; $$",
        f"CREATE TRIGGER grr_erase AFTER DELETE ON {TABLE} FOR EACH ROW EXECUTE FUNCTION grr_erase_fn()",
    )


def register(table: Table) -> None:
    for dialect in ("sqlite", "postgresql"):
        for statement in statements(dialect):
            event.listen(table, "after_create", DDL(statement).execute_if(dialect=dialect))
    for kind in ("binding", "immutable", "guard", "erase"):
        event.listen(
            table,
            "after_drop",
            DDL(f"DROP FUNCTION IF EXISTS grr_{kind}_fn()").execute_if(dialect="postgresql"),
        )
