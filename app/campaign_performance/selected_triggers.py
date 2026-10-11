# ruff: noqa: E501
# mypy: disable-error-code=no-untyped-call
"""DB immutable rows and raw-erasure export fencing; frozen into0091."""

from sqlalchemy import DDL, Table, event


def binding(name: str, dialect: str) -> str:
    def cell(path: str) -> str:
        if dialect == "sqlite":
            return f"json_extract(NEW.canonical_json, '$.{path}')"
        return "(NEW.canonical_json::jsonb #>> '{" + path.replace(".", ",") + "}')"

    if name == "customer_event_selection_current":
        return "EXISTS (SELECT 1 FROM customer_event_selections s WHERE s.id=NEW.selection_id AND s.payload_digest=NEW.selection_digest AND s.account_id=NEW.account_id AND s.workspace_id=NEW.workspace_id AND s.connection_id=NEW.connection_id)"
    length = (
        "length(CAST(NEW.canonical_json AS BLOB))"
        if dialect == "sqlite"
        else "octet_length(NEW.canonical_json)"
    )
    predicate = f"NEW.payload_bytes={length}"
    if name == "customer_event_selections":
        paths = {
            "id": "selection_id",
            "workspace_id": "scope.workspace_id",
            "account_id": "scope.account_id",
            "connection_id": "scope.connection_id",
            "confirmed_by_customer_id": "confirmed_by_customer_id",
        }
        schema = "inlet.customer-event-selection.v1"
        predicate += " AND EXISTS (SELECT 1 FROM customer_memberships m JOIN customer_users u ON u.id=m.user_id WHERE m.workspace_id=NEW.workspace_id AND m.user_id=NEW.confirmed_by_customer_id AND m.status='active' AND m.role='owner' AND u.status='active')"
    elif name == "selected_reporting_captures":
        paths = {
            "id": "request.capture_id",
            "workspace_id": "request.aggregate.scope.workspace_id",
            "account_id": "request.aggregate.scope.account_id",
            "connection_id": "request.aggregate.scope.connection_id",
            "selection_id": "request.selection.selection_id",
            "selection_digest": "request.selection_digest",
            "completion_id": "request.aggregate.completion_id",
            "request_digest": "request_digest",
        }
        schema = "inlet.selected-capture.v1"
        predicate += " AND EXISTS (SELECT 1 FROM customer_event_selections s WHERE s.id=NEW.selection_id AND s.connection_id=NEW.connection_id AND s.workspace_id=NEW.workspace_id AND s.account_id=NEW.account_id)"
    else:
        paths = {k: k for k in ("capture_id", "campaign_id", "metric_date", "native_campaign_id")}
        schema = "inlet.selected-campaign-day.v1"
        predicate += " AND EXISTS (SELECT 1 FROM campaigns c JOIN selected_reporting_captures h ON h.id=NEW.capture_id WHERE c.id=NEW.campaign_id AND c.account_id=NEW.account_id AND c.external_campaign_id=NEW.native_campaign_id AND h.workspace_id=NEW.workspace_id AND h.account_id=NEW.account_id)"
    if name == "selected_reporting_facts":
        platform = (
            "json_extract(h.canonical_json,'$.request.aggregate.scope.platform')"
            if dialect == "sqlite"
            else "(h.canonical_json::jsonb #>> '{request,aggregate,scope,platform}')"
        )
        predicate += f" AND EXISTS(SELECT 1 FROM selected_reporting_captures h JOIN campaigns c ON c.id=NEW.campaign_id AND c.account_id=NEW.account_id WHERE h.id=NEW.capture_id AND CAST(c.platform AS TEXT)={platform})"
    predicate += f" AND {cell('schema_version')}='{schema}'"
    for col, path in paths.items():
        predicate += f" AND CAST({cell(path)} AS TEXT)=CAST(NEW.{col} AS TEXT)"
    return predicate


def live_head(dialect: str) -> str:
    def field(path: str) -> str:
        if dialect == "sqlite":
            return f"json_extract(s.canonical_json,'$.scope.{path}')"
        return "(s.canonical_json::jsonb #>> '{scope," + path + "}')"

    tests = [
        f"CAST({field(k)} AS TEXT)=CAST({v} AS TEXT)"
        for k, v in {
            "privacy_revision": "w.export_privacy_revision",
            "connection_id": "a.connection_id",
            "native_account_id": "a.external_account_id",
            "platform": "a.platform",
            "currency": "a.currency_code",
            "time_zone": "a.time_zone",
        }.items()
    ]
    branches = []
    for platform, table, ref, native in (
        ("meta_ads", "meta_connections", "workspace_integration_id", "external_account_id"),
        ("google_ads", "google_customer_connections", "integration_id", "external_account_id"),
        ("tiktok_ads", "customer_source_connections", "integration_id", "external_id"),
    ):
        extra = " AND n.provider='tiktok_ads'" if platform == "tiktok_ads" else ""
        branches.append(
            f"(CAST(a.platform AS TEXT)='{platform}' AND EXISTS(SELECT 1 FROM {table} n WHERE n.workspace_id=a.workspace_id AND n.account_id=a.id AND CAST(n.id AS TEXT)={field('source_connection_ref')} AND CAST(n.generation AS TEXT)=CAST({field('generation')} AS TEXT) AND n.status='connected' AND n.error_code IS NULL AND n.{ref}=a.connection_id AND n.{native}=a.external_account_id{extra}))"
        )
    return (
        "EXISTS(SELECT 1 FROM customer_event_selections s JOIN advertising_accounts a ON a.id=s.account_id AND a.workspace_id=s.workspace_id JOIN workspaces w ON w.id=s.workspace_id JOIN workspace_integrations i ON i.id=a.connection_id AND i.workspace_id=a.workspace_id WHERE s.id=NEW.selection_id AND s.payload_digest=NEW.selection_digest AND s.account_id=NEW.account_id AND s.workspace_id=NEW.workspace_id AND s.connection_id=NEW.connection_id AND w.status='active' AND i.status='active' AND i.provider=CAST(a.platform AS TEXT) AND "
        + " AND ".join(tests)
        + " AND ("
        + " OR ".join(branches)
        + "))"
    )


def statements(name: str, dialect: str) -> tuple[str, ...]:
    head = name == "customer_event_selection_current"
    predicate = binding(name, dialect)
    if head:
        predicate += " AND NOT NEW.invalidated AND " + live_head(dialect)
    if dialect == "sqlite":
        predicate += " AND (SELECT foreign_keys FROM pragma_foreign_keys)=1"
    erase = (
        "DELETE FROM selected_reporting_captures WHERE id=OLD.capture_id AND workspace_id=OLD.workspace_id;"
        if name == "selected_reporting_facts"
        else ""
    )
    if head:
        erase += "DELETE FROM selected_reporting_captures WHERE workspace_id=OLD.workspace_id AND account_id=OLD.account_id;"
    erase += "DELETE FROM initial_calibration_runs WHERE workspace_id=OLD.workspace_id AND account_id=OLD.account_id;"
    erase += "UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id;"
    same_scope = "NEW.account_id=OLD.account_id AND NEW.workspace_id=OLD.workspace_id AND NEW.connection_id=OLD.connection_id"
    same_pointer = "NEW.selection_id=OLD.selection_id AND NEW.selection_digest=OLD.selection_digest"
    permitted = f"({same_scope}) AND (({same_pointer} AND NEW.invalidated=OLD.invalidated) OR ({same_pointer} AND NOT OLD.invalidated AND NEW.invalidated) OR (OLD.invalidated AND NOT NEW.invalidated AND NEW.selection_id<>OLD.selection_id AND {live_head(dialect)}))"
    update_check = f"NOT COALESCE(({permitted})," + ("0" if dialect == "sqlite" else "false") + ")"
    transition = "DELETE FROM selected_reporting_captures WHERE workspace_id=NEW.workspace_id AND account_id=NEW.account_id; DELETE FROM initial_calibration_runs WHERE workspace_id=NEW.workspace_id AND account_id=NEW.account_id; UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 WHERE id=NEW.workspace_id;"
    extras: tuple[str, ...] = ()
    if head and dialect == "sqlite":
        extras = (
            f"CREATE TRIGGER {name}_invalidate AFTER UPDATE ON {name} WHEN NOT OLD.invalidated AND NEW.invalidated BEGIN {transition} END",
        )
    elif head:
        extras = (
            f"CREATE FUNCTION {name}_invalidate_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NOT OLD.invalidated AND NEW.invalidated THEN {transition} END IF; RETURN NEW; END; $$",
            f"CREATE TRIGGER {name}_invalidate AFTER UPDATE ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_invalidate_fn()",
        )
    if dialect == "sqlite":
        return extras + (
            f"CREATE TRIGGER {name}_binding BEFORE INSERT ON {name} WHEN NOT COALESCE(({predicate}),0) BEGIN SELECT RAISE(ABORT,'selected binding mismatch'); END",
            f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} "
            + (f"WHEN {update_check} " if head else "")
            + "BEGIN SELECT RAISE(ABORT,'immutable selected reporting'); END",
            f"CREATE TRIGGER {name}_erase AFTER DELETE ON {name} BEGIN {erase} END",
        )
    return extras + (
        f"CREATE FUNCTION {name}_binding_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NOT COALESCE(({predicate}),false) THEN RAISE EXCEPTION 'selected binding mismatch'; END IF; RETURN NEW; END; $$",
        f"CREATE TRIGGER {name}_binding BEFORE INSERT ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_binding_fn()",
        f"CREATE FUNCTION {name}_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        + (
            f"PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; IF {update_check} THEN "
            if head
            else ""
        )
        + "RAISE EXCEPTION 'immutable selected reporting'; "
        + ("END IF; RETURN NEW; " if head else "")
        + "END; $$",
        f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_immutable_fn()",
        f"CREATE FUNCTION {name}_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; RETURN OLD; END; $$",
        f"CREATE TRIGGER {name}_guard BEFORE DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_guard_fn()",
        f"CREATE FUNCTION {name}_erase_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {erase} RETURN NULL; END; $$",
        f"CREATE TRIGGER {name}_erase AFTER DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_erase_fn()",
    )


def register(table: Table) -> None:
    for dialect in ("sqlite", "postgresql"):
        for sql in statements(table.name, dialect):
            event.listen(table, "after_create", DDL(sql).execute_if(dialect=dialect))
    for kind in ("binding", "immutable", "guard", "erase", "invalidate"):
        event.listen(
            table,
            "after_drop",
            DDL(f"DROP FUNCTION IF EXISTS {table.name}_{kind}_fn()").execute_if(
                dialect="postgresql"
            ),
        )
