# mypy: disable-error-code=no-untyped-call
"""Original-window and paired-stage bindings, shared with frozen migration DDL."""

from sqlalchemy import DDL, Table, event


def statements(name: str, dialect: str) -> tuple[str, ...]:
    def value(column: str, path: str) -> str:
        if dialect == "sqlite":
            return f"json_extract({column}, '$.{path}')"
        keys = path.split(".")
        return f"({column}::jsonb" + "".join(f"->'{k}'" for k in keys[:-1]) + f"->>'{keys[-1]}')"

    def size(column: str) -> str:
        return (
            f"length(CAST({column} AS BLOB))" if dialect == "sqlite" else f"octet_length({column})"
        )

    context = name == "meta_presence_stage_contexts"
    if context:

        def j(key: str) -> str:
            return value("NEW.canonical_json", key)

        keys = (
            "window_token",
            "workspace_id",
            "account_id",
            "integration_id",
            "native_advertiser_id",
            "generation",
            "privacy_revision",
            "starts_on",
            "ends_on",
        )
        same = " AND ".join(f"CAST({j(k)} AS TEXT)=CAST(NEW.{k} AS TEXT)" for k in keys)
        instant = (
            f"julianday({j('captured_at')})=julianday(NEW.captured_at)"
            if dialect == "sqlite"
            else f"{j('captured_at')}::timestamptz=NEW.captured_at"
        )
        interval = (
            "julianday(NEW.ends_on)-julianday(NEW.starts_on)"
            if dialect == "sqlite"
            else "NEW.ends_on-NEW.starts_on"
        )
        predicate = (
            f"NEW.payload_bytes={size('NEW.canonical_json')} AND {same} AND "
            f"{instant} AND {interval}<400 AND "
            f"{j('schema_version')}='inlet.meta-presence-window.v1' AND "
            f"CAST({j('nativeconnection_id')} AS TEXT)=CAST(NEW.connection_id AS "
            f"TEXT) AND EXISTS (SELECT 1 FROM meta_connections c JOIN "
            f"advertising_accounts a ON a.id=c.account_id JOIN workspaces w ON "
            f"w.id=c.workspace_id WHERE c.id=NEW.connection_id AND "
            f"c.workspace_id=NEW.workspace_id AND c.account_id=NEW.account_id AND "
            f"c.workspace_integration_id=NEW.integration_id AND "
            f"c.external_account_id=NEW.native_advertiser_id AND "
            f"c.generation=NEW.generation AND c.window_start=NEW.starts_on AND "
            f"c.window_end=NEW.ends_on AND c.status='connected' AND "
            f"w.export_privacy_revision=NEW.privacy_revision AND "
            f"a.workspace_id=NEW.workspace_id AND a.connection_id=NEW.integration_id "
            f"AND a.external_account_id=NEW.native_advertiser_id AND CAST(a.platform "
            f"AS TEXT)='meta_ads' AND a.currency_code={j('currency')} AND "
            f"a.time_zone={j('time_zone')} AND "
            f"((c.conversion_action_type={j('selected_event.native_event_id')} AND "
            f"{j('selected_event.provenance')}='explicit_selected') OR "
            f"(c.conversion_action_type IS NULL AND "
            f"{j('selected_event.native_event_id')} IS NULL AND "
            f"{j('selected_event.provenance')}='unavailable')))"
        )
    else:

        def j(key: str) -> str:
            return value("NEW.presence_json", key)

        day = j("metric_date") if dialect == "sqlite" else f"{j('metric_date')}::date"
        numeric = " AND ".join(
            (
                f"({j(field + '.presence')}!='present' OR CAST({j(field + '.value')} AS "
                f"NUMERIC)=NEW.{column})"
            )
            for field, column in (
                ("impressions", "impressions"),
                ("clicks", "clicks"),
                ("spend_micros", "cost_micros"),
                ("selected_conversions", "conversions"),
                ("selected_value_micros", "conversion_value_micros"),
            )
        )
        predicate = (
            f"(NEW.presence_context_token IS NULL AND NEW.presence_json IS NULL) OR "
            f"(NEW.presence_context_token IS NOT NULL AND NEW.presence_json IS NOT "
            f"NULL AND {size('NEW.presence_json')}<=4096 AND {numeric} AND EXISTS "
            f"(SELECT 1 FROM meta_presence_stage_contexts h JOIN campaigns c ON "
            f"c.account_id=h.account_id WHERE h.connection_id=NEW.connection_id AND "
            f"h.window_token=NEW.presence_context_token AND c.id=NEW.campaign_id AND "
            f"CAST(c.platform AS TEXT)='meta_ads' AND "
            f"c.external_campaign_id={j('native_campaign_id')} AND "
            f"NEW.metric_date={day} AND NEW.metric_date>=h.starts_on AND "
            f"NEW.metric_date<=h.ends_on))"
        )
    kinds = ("INSERT",) if context else ("INSERT", "UPDATE")
    result = []
    if dialect == "postgresql":
        result.append(
            f"CREATE FUNCTION {name}_presence_binding_fn() RETURNS trigger LANGUAGE "
            f"plpgsql AS $$ BEGIN IF NOT COALESCE(({predicate}),false) THEN RAISE "
            f"EXCEPTION 'Meta presence binding mismatch'; END IF; RETURN NEW; END; "
            f"$$"
        )
    for kind in kinds:
        trigger = f"{name}_presence_{kind.lower()}"
        if dialect == "sqlite":
            result.append(
                f"CREATE TRIGGER {trigger} BEFORE {kind} ON {name} WHEN NOT "
                f"COALESCE(({predicate}),0) BEGIN SELECT RAISE(ABORT,'Meta presence "
                f"binding mismatch'); END"
            )
        else:
            result.append(
                f"CREATE TRIGGER {trigger} BEFORE {kind} ON {name} FOR EACH ROW EXECUTE "
                f"FUNCTION {name}_presence_binding_fn()"
            )
    if context:
        if dialect == "sqlite":
            result.append(
                f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} BEGIN SELECT "
                f"RAISE(ABORT,'immutable Meta presence context'); END"
            )
        else:
            result += [
                (
                    f"CREATE FUNCTION {name}_presence_immutable_fn() RETURNS trigger "
                    f"LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable Meta presence "
                    f"context'; END; $$"
                ),
                (
                    f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} FOR EACH ROW "
                    f"EXECUTE FUNCTION {name}_presence_immutable_fn()"
                ),
            ]
    return tuple(result)


def register(table: Table) -> None:
    for dialect in ("sqlite", "postgresql"):
        for statement in statements(table.name, dialect):
            event.listen(table, "after_create", DDL(statement).execute_if(dialect=dialect))
    for kind in ("binding", "immutable"):
        event.listen(
            table,
            "after_drop",
            DDL(f"DROP FUNCTION IF EXISTS {table.name}_presence_{kind}_fn()").execute_if(
                dialect="postgresql"
            ),
        )
