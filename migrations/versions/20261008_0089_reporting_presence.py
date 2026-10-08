# ruff: noqa: E501
"""Finalized reporting presence, independent of legacy numeric manifests."""
import sqlalchemy as sa
from alembic import op

revision = "20261008_0089"
down_revision = "20261008_0088"
branch_labels = None
depends_on = None
TABLES = ("campaign_performance_semantics", "campaign_performance_metric_presence")


def upgrade() -> None:
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    connection = op.get_bind()
    if any(connection.scalar(sa.text(f"SELECT EXISTS(SELECT 1 FROM {name})")) for name in TABLES):
        raise RuntimeError("cannot discard retained reporting presence")
    for name in reversed(TABLES):
        op.drop_table(name)
        if connection.dialect.name == "postgresql":
            for kind in ("binding", "immutable"):
                op.execute(f"DROP FUNCTION IF EXISTS {name}_{kind}_fn()")


# Frozen DDL; never import current application code into historical migrations.
SQL = {'postgresql': ('\n'
                'CREATE TABLE campaign_performance_semantics (\n'
                '\tcompletion_id VARCHAR(32) NOT NULL, \n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\taccount_id INTEGER NOT NULL, \n'
                '\tconnection_id INTEGER NOT NULL, \n'
                '\tplatform VARCHAR(16) NOT NULL, \n'
                '\tsource_connection_ref VARCHAR(32) NOT NULL, \n'
                '\tgeneration INTEGER NOT NULL, \n'
                '\tprivacy_revision INTEGER NOT NULL, \n'
                '\trequested_starts_on DATE NOT NULL, \n'
                '\trequested_ends_on DATE NOT NULL, \n'
                '\tlegacy_manifest_digest VARCHAR(64) NOT NULL, \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tpayload_digest VARCHAR(64) NOT NULL, \n'
                '\tpayload_bytes INTEGER NOT NULL, \n'
                '\tfact_count INTEGER NOT NULL, \n'
                '\tfact_digest VARCHAR(64) NOT NULL, \n'
                '\tPRIMARY KEY (completion_id), \n'
                '\tFOREIGN KEY(completion_id, account_id, workspace_id) REFERENCES '
                'campaign_performance_completions (id, account_id, workspace_id) ON DELETE '
                'CASCADE, \n'
                '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
                'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
                '\tCONSTRAINT uq_presence_scope UNIQUE (completion_id, account_id, '
                'workspace_id), \n'
                '\tCONSTRAINT ck_presence_revisions CHECK (generation > 0 AND privacy_revision >= '
                '0), \n'
                '\tCONSTRAINT ck_presence_dates CHECK (requested_starts_on <= '
                'requested_ends_on), \n'
                '\tCONSTRAINT ck_presence_count CHECK (fact_count >= 0 AND fact_count <= '
                '100000), \n'
                '\tCONSTRAINT ck_presence_bytes CHECK (payload_bytes > 0 AND payload_bytes <= '
                '8192)\n'
                ')\n'
                '\n',
                'CREATE FUNCTION campaign_performance_semantics_binding_fn() RETURNS trigger '
                'LANGUAGE plpgsql AS $$ BEGIN IF NOT '
                'COALESCE((NEW.payload_bytes=octet_length(NEW.canonical_json) AND '
                "(NEW.canonical_json::jsonb->>'schema_version')='inlet.reporting-semantics.v1' AND "
                'NEW.requested_ends_on-NEW.requested_starts_on<400 AND EXISTS (SELECT 1 FROM '
                'campaign_performance_completions c JOIN advertising_accounts a ON '
                'a.id=c.account_id AND a.workspace_id=c.workspace_id WHERE c.id=NEW.completion_id '
                'AND c.account_id=NEW.account_id AND c.workspace_id=NEW.workspace_id AND '
                'a.connection_id=NEW.connection_id AND c.platform=NEW.platform AND CAST(a.platform '
                'AS TEXT)=NEW.platform AND c.source_connection_ref=NEW.source_connection_ref AND '
                'c.generation=NEW.generation AND c.privacy_revision=NEW.privacy_revision AND '
                'c.starts_on=NEW.requested_starts_on AND c.ends_on=NEW.requested_ends_on AND '
                'c.manifest_digest=NEW.legacy_manifest_digest AND c.row_count=NEW.fact_count AND '
                "c.query_version=(NEW.canonical_json::jsonb->>'query_descriptor') AND "
                "c.currency=(NEW.canonical_json::jsonb->>'currency') AND "
                "c.time_zone=(NEW.canonical_json::jsonb->>'time_zone') AND "
                "(NEW.canonical_json::jsonb->>'completed_at')::timestamptz=c.completed_at AND "
                "(((NEW.canonical_json::jsonb->'selected_event'->>'provenance')='explicit_selected' "
                'AND '
                "(NEW.canonical_json::jsonb->'selected_event'->>'native_event_id')=c.selected_event) "
                "OR ((NEW.canonical_json::jsonb->'selected_event'->>'provenance') IN "
                "('generic','unavailable') AND c.selected_event IS NULL))) AND "
                "CAST((NEW.canonical_json::jsonb->>'completion_id') AS "
                'TEXT)=CAST(NEW.completion_id AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'workspace_id') AS TEXT)=CAST(NEW.workspace_id "
                "AS TEXT) AND CAST((NEW.canonical_json::jsonb->>'account_id') AS "
                'TEXT)=CAST(NEW.account_id AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'connection_id') AS "
                'TEXT)=CAST(NEW.connection_id AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'platform') AS TEXT)=CAST(NEW.platform AS TEXT) "
                "AND CAST((NEW.canonical_json::jsonb->>'source_connection_ref') AS "
                'TEXT)=CAST(NEW.source_connection_ref AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'generation') AS TEXT)=CAST(NEW.generation AS "
                "TEXT) AND CAST((NEW.canonical_json::jsonb->>'privacy_revision') AS "
                'TEXT)=CAST(NEW.privacy_revision AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'requested_starts_on') AS "
                'TEXT)=CAST(NEW.requested_starts_on AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'requested_ends_on') AS "
                'TEXT)=CAST(NEW.requested_ends_on AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'legacy_manifest_digest') AS "
                'TEXT)=CAST(NEW.legacy_manifest_digest AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'fact_count') AS TEXT)=CAST(NEW.fact_count AS "
                "TEXT) AND CAST((NEW.canonical_json::jsonb->>'fact_digest') AS "
                "TEXT)=CAST(NEW.fact_digest AS TEXT)),false) THEN RAISE EXCEPTION 'reporting "
                "presence binding mismatch'; END IF; RETURN NEW; END; $$",
                'CREATE TRIGGER campaign_performance_semantics_binding BEFORE INSERT ON '
                'campaign_performance_semantics FOR EACH ROW EXECUTE FUNCTION '
                'campaign_performance_semantics_binding_fn()',
                'CREATE FUNCTION campaign_performance_semantics_immutable_fn() RETURNS trigger '
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable reporting presence'; END; "
                '$$',
                'CREATE TRIGGER campaign_performance_semantics_immutable BEFORE UPDATE ON '
                'campaign_performance_semantics FOR EACH ROW EXECUTE FUNCTION '
                'campaign_performance_semantics_immutable_fn()',
                '\n'
                'CREATE TABLE campaign_performance_metric_presence (\n'
                '\tcompletion_id VARCHAR(32) NOT NULL, \n'
                '\tcampaign_id INTEGER NOT NULL, \n'
                '\tmetric_date DATE NOT NULL, \n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\taccount_id INTEGER NOT NULL, \n'
                '\tnative_campaign_id VARCHAR(32) NOT NULL, \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tpayload_digest VARCHAR(64) NOT NULL, \n'
                '\tpayload_bytes INTEGER NOT NULL, \n'
                '\tPRIMARY KEY (completion_id, campaign_id, metric_date), \n'
                '\tFOREIGN KEY(completion_id, account_id, workspace_id) REFERENCES '
                'campaign_performance_semantics (completion_id, account_id, workspace_id) ON '
                'DELETE CASCADE, \n'
                '\tFOREIGN KEY(campaign_id, account_id) REFERENCES campaigns (id, account_id) ON '
                'DELETE CASCADE, \n'
                '\tCONSTRAINT uq_presence_native_day UNIQUE (completion_id, native_campaign_id, '
                'metric_date), \n'
                '\tCONSTRAINT ck_presence_fact_bytes CHECK (payload_bytes > 0 AND payload_bytes <= '
                '4096)\n'
                ')\n'
                '\n',
                'CREATE FUNCTION campaign_performance_metric_presence_binding_fn() RETURNS trigger '
                'LANGUAGE plpgsql AS $$ BEGIN IF NOT '
                'COALESCE((NEW.payload_bytes=octet_length(NEW.canonical_json) AND '
                "(NEW.canonical_json::jsonb->>'schema_version')='inlet.metric-presence.v1' AND "
                'EXISTS (SELECT 1 FROM campaign_performance_semantics h JOIN campaigns c ON '
                'c.id=NEW.campaign_id AND c.account_id=h.account_id WHERE '
                'h.completion_id=NEW.completion_id AND h.account_id=NEW.account_id AND '
                'h.workspace_id=NEW.workspace_id AND CAST(c.platform AS TEXT)=h.platform AND '
                'c.external_campaign_id=NEW.native_campaign_id AND '
                'NEW.metric_date>=h.requested_starts_on AND NEW.metric_date<=h.requested_ends_on '
                "AND NEW.metric_date>=(h.canonical_json::jsonb->>'actual_starts_on')::date AND "
                "NEW.metric_date<=(h.canonical_json::jsonb->>'actual_ends_on')::date) AND "
                "CAST((NEW.canonical_json::jsonb->>'completion_id') AS "
                'TEXT)=CAST(NEW.completion_id AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'workspace_id') AS TEXT)=CAST(NEW.workspace_id "
                "AS TEXT) AND CAST((NEW.canonical_json::jsonb->>'account_id') AS "
                'TEXT)=CAST(NEW.account_id AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'campaign_id') AS TEXT)=CAST(NEW.campaign_id AS "
                "TEXT) AND CAST((NEW.canonical_json::jsonb->>'metric_date') AS "
                'TEXT)=CAST(NEW.metric_date AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'native_campaign_id') AS "
                'TEXT)=CAST(NEW.native_campaign_id AS TEXT)),false) THEN RAISE EXCEPTION '
                "'reporting presence binding mismatch'; END IF; RETURN NEW; END; $$",
                'CREATE TRIGGER campaign_performance_metric_presence_binding BEFORE INSERT ON '
                'campaign_performance_metric_presence FOR EACH ROW EXECUTE FUNCTION '
                'campaign_performance_metric_presence_binding_fn()',
                'CREATE FUNCTION campaign_performance_metric_presence_immutable_fn() RETURNS '
                "trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable reporting "
                "presence'; END; $$",
                'CREATE TRIGGER campaign_performance_metric_presence_immutable BEFORE UPDATE ON '
                'campaign_performance_metric_presence FOR EACH ROW EXECUTE FUNCTION '
                'campaign_performance_metric_presence_immutable_fn()'),
 'sqlite': ('\n'
            'CREATE TABLE campaign_performance_semantics (\n'
            '\tcompletion_id VARCHAR(32) NOT NULL, \n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\taccount_id INTEGER NOT NULL, \n'
            '\tconnection_id INTEGER NOT NULL, \n'
            '\tplatform VARCHAR(16) NOT NULL, \n'
            '\tsource_connection_ref VARCHAR(32) NOT NULL, \n'
            '\tgeneration INTEGER NOT NULL, \n'
            '\tprivacy_revision INTEGER NOT NULL, \n'
            '\trequested_starts_on DATE NOT NULL, \n'
            '\trequested_ends_on DATE NOT NULL, \n'
            '\tlegacy_manifest_digest VARCHAR(64) NOT NULL, \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tpayload_digest VARCHAR(64) NOT NULL, \n'
            '\tpayload_bytes INTEGER NOT NULL, \n'
            '\tfact_count INTEGER NOT NULL, \n'
            '\tfact_digest VARCHAR(64) NOT NULL, \n'
            '\tPRIMARY KEY (completion_id), \n'
            '\tFOREIGN KEY(completion_id, account_id, workspace_id) REFERENCES '
            'campaign_performance_completions (id, account_id, workspace_id) ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
            'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
            '\tCONSTRAINT uq_presence_scope UNIQUE (completion_id, account_id, workspace_id), \n'
            '\tCONSTRAINT ck_presence_revisions CHECK (generation > 0 AND privacy_revision >= '
            '0), \n'
            '\tCONSTRAINT ck_presence_dates CHECK (requested_starts_on <= requested_ends_on), \n'
            '\tCONSTRAINT ck_presence_count CHECK (fact_count >= 0 AND fact_count <= 100000), \n'
            '\tCONSTRAINT ck_presence_bytes CHECK (payload_bytes > 0 AND payload_bytes <= 8192)\n'
            ')\n'
            '\n',
            'CREATE TRIGGER campaign_performance_semantics_binding BEFORE INSERT ON '
            'campaign_performance_semantics WHEN NOT '
            'COALESCE((NEW.payload_bytes=length(CAST(NEW.canonical_json AS BLOB)) AND '
            "json_extract(NEW.canonical_json, '$.schema_version')='inlet.reporting-semantics.v1' "
            'AND julianday(NEW.requested_ends_on)-julianday(NEW.requested_starts_on)<400 AND '
            'EXISTS (SELECT 1 FROM campaign_performance_completions c JOIN advertising_accounts a '
            'ON a.id=c.account_id AND a.workspace_id=c.workspace_id WHERE c.id=NEW.completion_id '
            'AND c.account_id=NEW.account_id AND c.workspace_id=NEW.workspace_id AND '
            'a.connection_id=NEW.connection_id AND c.platform=NEW.platform AND CAST(a.platform AS '
            'TEXT)=NEW.platform AND c.source_connection_ref=NEW.source_connection_ref AND '
            'c.generation=NEW.generation AND c.privacy_revision=NEW.privacy_revision AND '
            'c.starts_on=NEW.requested_starts_on AND c.ends_on=NEW.requested_ends_on AND '
            'c.manifest_digest=NEW.legacy_manifest_digest AND c.row_count=NEW.fact_count AND '
            "c.query_version=json_extract(NEW.canonical_json, '$.query_descriptor') AND "
            "c.currency=json_extract(NEW.canonical_json, '$.currency') AND "
            "c.time_zone=json_extract(NEW.canonical_json, '$.time_zone') AND "
            'julianday(json_extract(NEW.canonical_json, '
            "'$.completed_at'))=julianday(c.completed_at) AND ((json_extract(NEW.canonical_json, "
            "'$.selected_event.provenance')='explicit_selected' AND "
            'json_extract(NEW.canonical_json, '
            "'$.selected_event.native_event_id')=c.selected_event) OR "
            "(json_extract(NEW.canonical_json, '$.selected_event.provenance') IN "
            "('generic','unavailable') AND c.selected_event IS NULL))) AND "
            "CAST(json_extract(NEW.canonical_json, '$.completion_id') AS "
            'TEXT)=CAST(NEW.completion_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.workspace_id') AS TEXT)=CAST(NEW.workspace_id AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.account_id') AS TEXT)=CAST(NEW.account_id AS "
            "TEXT) AND CAST(json_extract(NEW.canonical_json, '$.connection_id') AS "
            'TEXT)=CAST(NEW.connection_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.platform') AS TEXT)=CAST(NEW.platform AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.source_connection_ref') AS "
            'TEXT)=CAST(NEW.source_connection_ref AS TEXT) AND '
            "CAST(json_extract(NEW.canonical_json, '$.generation') AS TEXT)=CAST(NEW.generation AS "
            "TEXT) AND CAST(json_extract(NEW.canonical_json, '$.privacy_revision') AS "
            'TEXT)=CAST(NEW.privacy_revision AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.requested_starts_on') AS TEXT)=CAST(NEW.requested_starts_on AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.requested_ends_on') AS "
            'TEXT)=CAST(NEW.requested_ends_on AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.legacy_manifest_digest') AS TEXT)=CAST(NEW.legacy_manifest_digest AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.fact_count') AS TEXT)=CAST(NEW.fact_count AS "
            "TEXT) AND CAST(json_extract(NEW.canonical_json, '$.fact_digest') AS "
            "TEXT)=CAST(NEW.fact_digest AS TEXT)),0) BEGIN SELECT RAISE(ABORT,'reporting presence "
            "binding mismatch'); END",
            'CREATE TRIGGER campaign_performance_semantics_immutable BEFORE UPDATE ON '
            "campaign_performance_semantics BEGIN SELECT RAISE(ABORT,'immutable reporting "
            "presence'); END",
            '\n'
            'CREATE TABLE campaign_performance_metric_presence (\n'
            '\tcompletion_id VARCHAR(32) NOT NULL, \n'
            '\tcampaign_id INTEGER NOT NULL, \n'
            '\tmetric_date DATE NOT NULL, \n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\taccount_id INTEGER NOT NULL, \n'
            '\tnative_campaign_id VARCHAR(32) NOT NULL, \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tpayload_digest VARCHAR(64) NOT NULL, \n'
            '\tpayload_bytes INTEGER NOT NULL, \n'
            '\tPRIMARY KEY (completion_id, campaign_id, metric_date), \n'
            '\tFOREIGN KEY(completion_id, account_id, workspace_id) REFERENCES '
            'campaign_performance_semantics (completion_id, account_id, workspace_id) ON DELETE '
            'CASCADE, \n'
            '\tFOREIGN KEY(campaign_id, account_id) REFERENCES campaigns (id, account_id) ON '
            'DELETE CASCADE, \n'
            '\tCONSTRAINT uq_presence_native_day UNIQUE (completion_id, native_campaign_id, '
            'metric_date), \n'
            '\tCONSTRAINT ck_presence_fact_bytes CHECK (payload_bytes > 0 AND payload_bytes <= '
            '4096)\n'
            ')\n'
            '\n',
            'CREATE TRIGGER campaign_performance_metric_presence_binding BEFORE INSERT ON '
            'campaign_performance_metric_presence WHEN NOT '
            'COALESCE((NEW.payload_bytes=length(CAST(NEW.canonical_json AS BLOB)) AND '
            "json_extract(NEW.canonical_json, '$.schema_version')='inlet.metric-presence.v1' AND "
            'EXISTS (SELECT 1 FROM campaign_performance_semantics h JOIN campaigns c ON '
            'c.id=NEW.campaign_id AND c.account_id=h.account_id WHERE '
            'h.completion_id=NEW.completion_id AND h.account_id=NEW.account_id AND '
            'h.workspace_id=NEW.workspace_id AND CAST(c.platform AS TEXT)=h.platform AND '
            'c.external_campaign_id=NEW.native_campaign_id AND '
            'NEW.metric_date>=h.requested_starts_on AND NEW.metric_date<=h.requested_ends_on AND '
            "NEW.metric_date>=json_extract(h.canonical_json, '$.actual_starts_on') AND "
            "NEW.metric_date<=json_extract(h.canonical_json, '$.actual_ends_on')) AND "
            "CAST(json_extract(NEW.canonical_json, '$.completion_id') AS "
            'TEXT)=CAST(NEW.completion_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.workspace_id') AS TEXT)=CAST(NEW.workspace_id AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.account_id') AS TEXT)=CAST(NEW.account_id AS "
            "TEXT) AND CAST(json_extract(NEW.canonical_json, '$.campaign_id') AS "
            'TEXT)=CAST(NEW.campaign_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.metric_date') AS TEXT)=CAST(NEW.metric_date AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.native_campaign_id') AS "
            "TEXT)=CAST(NEW.native_campaign_id AS TEXT)),0) BEGIN SELECT RAISE(ABORT,'reporting "
            "presence binding mismatch'); END",
            'CREATE TRIGGER campaign_performance_metric_presence_immutable BEFORE UPDATE ON '
            "campaign_performance_metric_presence BEGIN SELECT RAISE(ABORT,'immutable reporting "
            "presence'); END")}
