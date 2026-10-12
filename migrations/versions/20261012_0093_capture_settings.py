# ruff: noqa: E501
"""Admit versioned capture settings without rewriting retained rows or other fences."""

import sqlalchemy as sa
from alembic import op

revision = "20261012_0093"
down_revision = "20261011_0092"
branch_labels = None
depends_on = None


def replace_binding(sql: tuple[str, ...]) -> None:
    dialect = op.get_bind().dialect.name
    suffix = " ON selected_reporting_captures" if dialect == "postgresql" else ""
    op.execute("DROP TRIGGER selected_reporting_captures_binding" + suffix)
    if dialect == "postgresql":
        op.execute("DROP FUNCTION selected_reporting_captures_binding_fn()")
    for statement in sql:
        op.execute(statement)


def upgrade() -> None:
    replace_binding(SQL[op.get_bind().dialect.name])


def downgrade() -> None:
    db = op.get_bind()
    version = (
        "json_extract(canonical_json, '$.schema_version')"
        if db.dialect.name == "sqlite"
        else "(canonical_json::jsonb #>> '{schema_version}')"
    )
    if (
        db.execute(
            sa.text(
                "SELECT 1 FROM selected_reporting_captures WHERE COALESCE("
                + version
                + ", '') <> 'inlet.selected-capture.v1' LIMIT 1"
            )
        ).first()
        is not None
    ):
        raise RuntimeError("capture settings require reader-capable migration0093")
    replace_binding(PRIOR_SQL[db.dialect.name])


SQL = {
    "postgresql": (
        "CREATE FUNCTION selected_reporting_captures_binding_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF NOT "
        "COALESCE((NEW.payload_bytes=octet_length(NEW.canonical_json) AND EXISTS (SELECT "
        "1 FROM customer_event_selections s WHERE s.id=NEW.selection_id AND "
        "s.connection_id=NEW.connection_id AND s.workspace_id=NEW.workspace_id AND "
        "s.account_id=NEW.account_id) AND (((NEW.canonical_json::jsonb #>> "
        "'{schema_version}')='inlet.selected-capture.v1' AND (NEW.canonical_json::jsonb "
        "#>> '{request,schema_version}')='inlet.selected-capture-request.v1' AND "
        "jsonb_typeof(NEW.canonical_json::jsonb #> '{request,settings}') IS NULL) OR "
        "((NEW.canonical_json::jsonb #>> '{schema_version}')='inlet.selected-capture.v2' "
        "AND (NEW.canonical_json::jsonb #>> "
        "'{request,schema_version}')='inlet.selected-capture-request.v2' AND "
        "jsonb_typeof(NEW.canonical_json::jsonb #> '{request,settings}')='object' AND "
        "(NEW.canonical_json::jsonb #>> "
        "'{request,settings,schema_version}')='inlet.capture-settings.v1')) AND "
        "CAST((NEW.canonical_json::jsonb #>> '{request,capture_id}') AS TEXT)=CAST(NEW.id "
        "AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
        "'{request,aggregate,scope,workspace_id}') AS TEXT)=CAST(NEW.workspace_id AS "
        "TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
        "'{request,aggregate,scope,account_id}') AS TEXT)=CAST(NEW.account_id AS TEXT) "
        "AND CAST((NEW.canonical_json::jsonb #>> "
        "'{request,aggregate,scope,connection_id}') AS TEXT)=CAST(NEW.connection_id AS "
        "TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
        "'{request,selection,selection_id}') AS TEXT)=CAST(NEW.selection_id AS TEXT) AND "
        "CAST((NEW.canonical_json::jsonb #>> '{request,selection_digest}') AS "
        "TEXT)=CAST(NEW.selection_digest AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
        "'{request,aggregate,completion_id}') AS TEXT)=CAST(NEW.completion_id AS TEXT) "
        "AND CAST((NEW.canonical_json::jsonb #>> '{request_digest}') AS "
        "TEXT)=CAST(NEW.request_digest AS TEXT)),false) THEN RAISE EXCEPTION 'selected "
        "binding mismatch'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER selected_reporting_captures_binding BEFORE INSERT ON "
        "selected_reporting_captures FOR EACH ROW EXECUTE FUNCTION "
        "selected_reporting_captures_binding_fn()",
    ),
    "sqlite": (
        "CREATE TRIGGER selected_reporting_captures_binding BEFORE INSERT ON "
        "selected_reporting_captures WHEN NOT "
        "COALESCE((NEW.payload_bytes=length(CAST(NEW.canonical_json AS BLOB)) AND EXISTS "
        "(SELECT 1 FROM customer_event_selections s WHERE s.id=NEW.selection_id AND "
        "s.connection_id=NEW.connection_id AND s.workspace_id=NEW.workspace_id AND "
        "s.account_id=NEW.account_id) AND ((json_extract(NEW.canonical_json, "
        "'$.schema_version')='inlet.selected-capture.v1' AND json_extract(NEW.canonical_json, "
        "'$.request.schema_version')='inlet.selected-capture-request.v1' AND "
        "json_type(NEW.canonical_json, '$.request.settings') IS NULL) OR "
        "(json_extract(NEW.canonical_json, '$.schema_version')='inlet.selected-capture.v2' "
        "AND json_extract(NEW.canonical_json, "
        "'$.request.schema_version')='inlet.selected-capture-request.v2' AND "
        "json_type(NEW.canonical_json, '$.request.settings')='object' AND "
        "json_extract(NEW.canonical_json, "
        "'$.request.settings.schema_version')='inlet.capture-settings.v1')) AND "
        "CAST(json_extract(NEW.canonical_json, '$.request.capture_id') AS TEXT)=CAST(NEW.id "
        "AS TEXT) AND CAST(json_extract(NEW.canonical_json, "
        "'$.request.aggregate.scope.workspace_id') AS TEXT)=CAST(NEW.workspace_id AS TEXT) "
        "AND CAST(json_extract(NEW.canonical_json, '$.request.aggregate.scope.account_id') AS "
        "TEXT)=CAST(NEW.account_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, "
        "'$.request.aggregate.scope.connection_id') AS TEXT)=CAST(NEW.connection_id AS TEXT) "
        "AND CAST(json_extract(NEW.canonical_json, '$.request.selection.selection_id') AS "
        "TEXT)=CAST(NEW.selection_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, "
        "'$.request.selection_digest') AS TEXT)=CAST(NEW.selection_digest AS TEXT) AND "
        "CAST(json_extract(NEW.canonical_json, '$.request.aggregate.completion_id') AS "
        "TEXT)=CAST(NEW.completion_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, "
        "'$.request_digest') AS TEXT)=CAST(NEW.request_digest AS TEXT) AND (SELECT "
        "foreign_keys FROM pragma_foreign_keys)=1),0) BEGIN SELECT RAISE(ABORT,'selected "
        "binding mismatch'); END",
    ),
}

PRIOR_SQL = {
    "postgresql": (
        "CREATE FUNCTION selected_reporting_captures_binding_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF NOT "
        "COALESCE((NEW.payload_bytes=octet_length(NEW.canonical_json) AND EXISTS (SELECT "
        "1 FROM customer_event_selections s WHERE s.id=NEW.selection_id AND "
        "s.connection_id=NEW.connection_id AND s.workspace_id=NEW.workspace_id AND "
        "s.account_id=NEW.account_id) AND (NEW.canonical_json::jsonb #>> "
        "'{schema_version}')='inlet.selected-capture.v1' AND "
        "CAST((NEW.canonical_json::jsonb #>> '{request,capture_id}') AS TEXT)=CAST(NEW.id "
        "AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
        "'{request,aggregate,scope,workspace_id}') AS TEXT)=CAST(NEW.workspace_id AS "
        "TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
        "'{request,aggregate,scope,account_id}') AS TEXT)=CAST(NEW.account_id AS TEXT) "
        "AND CAST((NEW.canonical_json::jsonb #>> "
        "'{request,aggregate,scope,connection_id}') AS TEXT)=CAST(NEW.connection_id AS "
        "TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
        "'{request,selection,selection_id}') AS TEXT)=CAST(NEW.selection_id AS TEXT) AND "
        "CAST((NEW.canonical_json::jsonb #>> '{request,selection_digest}') AS "
        "TEXT)=CAST(NEW.selection_digest AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
        "'{request,aggregate,completion_id}') AS TEXT)=CAST(NEW.completion_id AS TEXT) "
        "AND CAST((NEW.canonical_json::jsonb #>> '{request_digest}') AS "
        "TEXT)=CAST(NEW.request_digest AS TEXT)),false) THEN RAISE EXCEPTION 'selected "
        "binding mismatch'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER selected_reporting_captures_binding BEFORE INSERT ON "
        "selected_reporting_captures FOR EACH ROW EXECUTE FUNCTION "
        "selected_reporting_captures_binding_fn()",
    ),
    "sqlite": (
        "CREATE TRIGGER selected_reporting_captures_binding BEFORE INSERT ON "
        "selected_reporting_captures WHEN NOT "
        "COALESCE((NEW.payload_bytes=length(CAST(NEW.canonical_json AS BLOB)) AND EXISTS "
        "(SELECT 1 FROM customer_event_selections s WHERE s.id=NEW.selection_id AND "
        "s.connection_id=NEW.connection_id AND s.workspace_id=NEW.workspace_id AND "
        "s.account_id=NEW.account_id) AND json_extract(NEW.canonical_json, "
        "'$.schema_version')='inlet.selected-capture.v1' AND "
        "CAST(json_extract(NEW.canonical_json, '$.request.capture_id') AS TEXT)=CAST(NEW.id "
        "AS TEXT) AND CAST(json_extract(NEW.canonical_json, "
        "'$.request.aggregate.scope.workspace_id') AS TEXT)=CAST(NEW.workspace_id AS TEXT) "
        "AND CAST(json_extract(NEW.canonical_json, '$.request.aggregate.scope.account_id') AS "
        "TEXT)=CAST(NEW.account_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, "
        "'$.request.aggregate.scope.connection_id') AS TEXT)=CAST(NEW.connection_id AS TEXT) "
        "AND CAST(json_extract(NEW.canonical_json, '$.request.selection.selection_id') AS "
        "TEXT)=CAST(NEW.selection_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, "
        "'$.request.selection_digest') AS TEXT)=CAST(NEW.selection_digest AS TEXT) AND "
        "CAST(json_extract(NEW.canonical_json, '$.request.aggregate.completion_id') AS "
        "TEXT)=CAST(NEW.completion_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, "
        "'$.request_digest') AS TEXT)=CAST(NEW.request_digest AS TEXT) AND (SELECT "
        "foreign_keys FROM pragma_foreign_keys)=1),0) BEGIN SELECT RAISE(ABORT,'selected "
        "binding mismatch'); END",
    ),
}
