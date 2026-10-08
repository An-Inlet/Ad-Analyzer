# mypy: disable-error-code=no-untyped-call
"""Frozen-compatible insert binding and UPDATE refusal for finalized presence."""

from sqlalchemy import DDL, Table, event


def statements(name: str, dialect: str) -> tuple[str, ...]:
    def cell(key: str) -> str:
        return (
            f"json_extract(NEW.canonical_json, '$.{key}')"
            if dialect == "sqlite"
            else f"(NEW.canonical_json::jsonb->>'{key}')"
        )

    def same(key: str) -> str:
        # Text casts avoid dialect-specific JSON number coercion.
        return f"CAST({cell(key)} AS TEXT)=CAST(NEW.{key} AS TEXT)"

    byte_length = (
        "length(CAST(NEW.canonical_json AS BLOB))"
        if dialect == "sqlite"
        else "octet_length(NEW.canonical_json)"
    )
    columns = ["completion_id", "workspace_id", "account_id"]
    predicate = f"NEW.payload_bytes={byte_length}"
    if name == "campaign_performance_semantics":
        columns += [
            "connection_id",
            "platform",
            "source_connection_ref",
            "generation",
            "privacy_revision",
            "requested_starts_on",
            "requested_ends_on",
            "legacy_manifest_digest",
            "fact_count",
            "fact_digest",
        ]
        interval = (
            "julianday(NEW.requested_ends_on)-julianday(NEW.requested_starts_on)"
            if dialect == "sqlite"
            else "NEW.requested_ends_on-NEW.requested_starts_on"
        )
        instant = (
            f"julianday({cell('completed_at')})=julianday(c.completed_at)"
            if dialect == "sqlite"
            else f"{cell('completed_at')}::timestamptz=c.completed_at"
        )
        event_id = (
            "json_extract(NEW.canonical_json, '$.selected_event.native_event_id')"
            if dialect == "sqlite"
            else "(NEW.canonical_json::jsonb->'selected_event'->>'native_event_id')"
        )
        provenance = (
            "json_extract(NEW.canonical_json, '$.selected_event.provenance')"
            if dialect == "sqlite"
            else "(NEW.canonical_json::jsonb->'selected_event'->>'provenance')"
        )
        predicate += (
            f" AND {cell('schema_version')}='inlet.reporting-semantics.v1' AND {interval}<400"
            " AND EXISTS (SELECT 1 FROM campaign_performance_completions c "
            "JOIN advertising_accounts a ON a.id=c.account_id AND a.workspace_id=c.workspace_id "
            "WHERE c.id=NEW.completion_id AND c.account_id=NEW.account_id "
            "AND c.workspace_id=NEW.workspace_id AND a.connection_id=NEW.connection_id "
            "AND c.platform=NEW.platform AND CAST(a.platform AS TEXT)=NEW.platform "
            "AND c.source_connection_ref=NEW.source_connection_ref AND c.generation=NEW.generation "
            "AND c.privacy_revision=NEW.privacy_revision AND c.starts_on=NEW.requested_starts_on "
            "AND c.ends_on=NEW.requested_ends_on AND c.manifest_digest=NEW.legacy_manifest_digest "
            f"AND c.row_count=NEW.fact_count AND c.query_version={cell('query_descriptor')} "
            f"AND c.currency={cell('currency')} AND c.time_zone={cell('time_zone')} AND {instant} "
            f"AND (({provenance}='explicit_selected' AND {event_id}=c.selected_event) "
            f"OR ({provenance} IN ('generic','unavailable') AND c.selected_event IS NULL)))"
        )
    else:
        columns += ["campaign_id", "metric_date", "native_campaign_id"]
        actual_start = (
            "json_extract(h.canonical_json, '$.actual_starts_on')"
            if dialect == "sqlite"
            else "(h.canonical_json::jsonb->>'actual_starts_on')::date"
        )
        actual_end = (
            "json_extract(h.canonical_json, '$.actual_ends_on')"
            if dialect == "sqlite"
            else "(h.canonical_json::jsonb->>'actual_ends_on')::date"
        )
        predicate += (
            f" AND {cell('schema_version')}='inlet.metric-presence.v1'"
            " AND EXISTS (SELECT 1 FROM campaign_performance_semantics h "
            "JOIN campaigns c ON c.id=NEW.campaign_id AND c.account_id=h.account_id "
            "WHERE h.completion_id=NEW.completion_id AND h.account_id=NEW.account_id "
            "AND h.workspace_id=NEW.workspace_id AND CAST(c.platform AS TEXT)=h.platform "
            "AND c.external_campaign_id=NEW.native_campaign_id "
            "AND NEW.metric_date>=h.requested_starts_on AND NEW.metric_date<=h.requested_ends_on "
            f"AND NEW.metric_date>={actual_start} AND NEW.metric_date<={actual_end})"
        )
    predicate += " AND " + " AND ".join(same(key) for key in columns)
    if dialect == "sqlite":
        return (
            f"CREATE TRIGGER {name}_binding BEFORE INSERT ON {name} "
            f"WHEN NOT COALESCE(({predicate}),0) "
            "BEGIN SELECT RAISE(ABORT,'reporting presence binding mismatch'); END",
            f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} "
            "BEGIN SELECT RAISE(ABORT,'immutable reporting presence'); END",
        )
    return (
        f"CREATE FUNCTION {name}_binding_fn() RETURNS trigger LANGUAGE plpgsql AS $$ "
        f"BEGIN IF NOT COALESCE(({predicate}),false) THEN "
        "RAISE EXCEPTION 'reporting presence binding mismatch'; END IF; RETURN NEW; END; $$",
        f"CREATE TRIGGER {name}_binding BEFORE INSERT ON {name} FOR EACH ROW "
        f"EXECUTE FUNCTION {name}_binding_fn()",
        f"CREATE FUNCTION {name}_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION 'immutable reporting presence'; END; $$",
        f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} FOR EACH ROW "
        f"EXECUTE FUNCTION {name}_immutable_fn()",
    )


def register(table: Table) -> None:
    for dialect in ("sqlite", "postgresql"):
        for statement in statements(table.name, dialect):
            event.listen(table, "after_create", DDL(statement).execute_if(dialect=dialect))
    for kind in ("binding", "immutable"):
        event.listen(
            table,
            "after_drop",
            DDL(f"DROP FUNCTION IF EXISTS {table.name}_{kind}_fn()").execute_if(
                dialect="postgresql"
            ),
        )
