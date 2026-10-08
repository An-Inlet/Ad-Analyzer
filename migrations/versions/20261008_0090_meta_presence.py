# ruff: noqa: E501
"""Original Meta window metadata and paired ephemeral presence staging."""
import sqlalchemy as sa
from alembic import op

revision = "20261008_0090"
down_revision = "20261008_0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    db = op.get_bind()
    if db.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM meta_presence_stage_contexts)")) or db.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM meta_staged_metrics WHERE presence_context_token IS NOT NULL OR presence_json IS NOT NULL)")):
        raise RuntimeError("cannot discard Meta window presence")
    for statement in DOWN[db.dialect.name]:
        op.execute(statement)


# Frozen SQL, independent of future application metadata.
SQL = {'postgresql': ('\n'
                'CREATE TABLE meta_presence_stage_contexts (\n'
                '\tconnection_id INTEGER NOT NULL, \n'
                '\twindow_token VARCHAR(32) NOT NULL, \n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\taccount_id INTEGER NOT NULL, \n'
                '\tintegration_id INTEGER NOT NULL, \n'
                '\tnative_advertiser_id VARCHAR(32) NOT NULL, \n'
                '\tgeneration INTEGER NOT NULL, \n'
                '\tprivacy_revision INTEGER NOT NULL, \n'
                '\tstarts_on DATE NOT NULL, \n'
                '\tends_on DATE NOT NULL, \n'
                '\tcaptured_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tpayload_digest VARCHAR(64) NOT NULL, \n'
                '\tpayload_bytes INTEGER NOT NULL, \n'
                '\tPRIMARY KEY (connection_id), \n'
                '\tFOREIGN KEY(connection_id, workspace_id) REFERENCES meta_connections (id, '
                'workspace_id) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(account_id, workspace_id, integration_id) REFERENCES '
                'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
                '\tCONSTRAINT uq_meta_presence_token UNIQUE (connection_id, window_token), \n'
                '\tCONSTRAINT ck_meta_presence_revision CHECK (generation > 0 AND '
                'privacy_revision >= 0), \n'
                '\tCONSTRAINT ck_meta_presence_dates CHECK (starts_on <= ends_on), \n'
                '\tCONSTRAINT ck_meta_presence_token_length CHECK (length(window_token) = '
                '32), \n'
                '\tCONSTRAINT ck_meta_presence_bytes CHECK (payload_bytes > 0 AND '
                'payload_bytes <= 8192)\n'
                ')\n'
                '\n',
                'ALTER TABLE meta_staged_metrics ADD COLUMN presence_context_token '
                'VARCHAR(32)',
                'ALTER TABLE meta_staged_metrics ADD COLUMN presence_json TEXT',
                'ALTER TABLE meta_staged_metrics ADD CONSTRAINT ck_meta_presence_pair CHECK '
                '((presence_context_token IS NULL AND presence_json IS NULL) OR '
                '(presence_context_token IS NOT NULL AND presence_json IS NOT NULL))',
                'ALTER TABLE meta_staged_metrics ADD CONSTRAINT '
                'fk_meta_staged_presence_context FOREIGN KEY '
                '(connection_id,presence_context_token) REFERENCES '
                'meta_presence_stage_contexts(connection_id,window_token) ON DELETE RESTRICT',
                'CREATE FUNCTION meta_presence_stage_contexts_presence_binding_fn() RETURNS '
                'trigger LANGUAGE plpgsql AS $$ BEGIN IF NOT '
                'COALESCE((NEW.payload_bytes=octet_length(NEW.canonical_json) AND '
                "CAST((NEW.canonical_json::jsonb->>'window_token') AS "
                'TEXT)=CAST(NEW.window_token AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'workspace_id') AS "
                'TEXT)=CAST(NEW.workspace_id AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'account_id') AS TEXT)=CAST(NEW.account_id "
                "AS TEXT) AND CAST((NEW.canonical_json::jsonb->>'integration_id') AS "
                'TEXT)=CAST(NEW.integration_id AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'native_advertiser_id') AS "
                'TEXT)=CAST(NEW.native_advertiser_id AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'generation') AS TEXT)=CAST(NEW.generation "
                "AS TEXT) AND CAST((NEW.canonical_json::jsonb->>'privacy_revision') AS "
                'TEXT)=CAST(NEW.privacy_revision AS TEXT) AND '
                "CAST((NEW.canonical_json::jsonb->>'starts_on') AS TEXT)=CAST(NEW.starts_on "
                "AS TEXT) AND CAST((NEW.canonical_json::jsonb->>'ends_on') AS "
                'TEXT)=CAST(NEW.ends_on AS TEXT) AND '
                "(NEW.canonical_json::jsonb->>'captured_at')::timestamptz=NEW.captured_at AND "
                'NEW.ends_on-NEW.starts_on<400 AND '
                "(NEW.canonical_json::jsonb->>'schema_version')='inlet.meta-presence-window.v1' "
                "AND CAST((NEW.canonical_json::jsonb->>'nativeconnection_id') AS "
                'TEXT)=CAST(NEW.connection_id AS TEXT) AND EXISTS (SELECT 1 FROM '
                'meta_connections c JOIN advertising_accounts a ON a.id=c.account_id JOIN '
                'workspaces w ON w.id=c.workspace_id WHERE c.id=NEW.connection_id AND '
                'c.workspace_id=NEW.workspace_id AND c.account_id=NEW.account_id AND '
                'c.workspace_integration_id=NEW.integration_id AND '
                'c.external_account_id=NEW.native_advertiser_id AND '
                'c.generation=NEW.generation AND c.window_start=NEW.starts_on AND '
                "c.window_end=NEW.ends_on AND c.status='connected' AND "
                'w.export_privacy_revision=NEW.privacy_revision AND '
                'a.workspace_id=NEW.workspace_id AND a.connection_id=NEW.integration_id AND '
                'a.external_account_id=NEW.native_advertiser_id AND CAST(a.platform AS '
                "TEXT)='meta_ads' AND "
                "a.currency_code=(NEW.canonical_json::jsonb->>'currency') AND "
                "a.time_zone=(NEW.canonical_json::jsonb->>'time_zone') AND "
                "((c.conversion_action_type=(NEW.canonical_json::jsonb->'selected_event'->>'native_event_id') "
                'AND '
                "(NEW.canonical_json::jsonb->'selected_event'->>'provenance')='explicit_selected') "
                'OR (c.conversion_action_type IS NULL AND '
                "(NEW.canonical_json::jsonb->'selected_event'->>'native_event_id') IS NULL "
                'AND '
                "(NEW.canonical_json::jsonb->'selected_event'->>'provenance')='unavailable')))),false) "
                "THEN RAISE EXCEPTION 'Meta presence binding mismatch'; END IF; RETURN NEW; "
                'END; $$',
                'CREATE TRIGGER meta_presence_stage_contexts_presence_insert BEFORE INSERT ON '
                'meta_presence_stage_contexts FOR EACH ROW EXECUTE FUNCTION '
                'meta_presence_stage_contexts_presence_binding_fn()',
                'CREATE FUNCTION meta_presence_stage_contexts_presence_immutable_fn() RETURNS '
                "trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable Meta "
                "presence context'; END; $$",
                'CREATE TRIGGER meta_presence_stage_contexts_immutable BEFORE UPDATE ON '
                'meta_presence_stage_contexts FOR EACH ROW EXECUTE FUNCTION '
                'meta_presence_stage_contexts_presence_immutable_fn()',
                'CREATE FUNCTION meta_staged_metrics_presence_binding_fn() RETURNS trigger '
                'LANGUAGE plpgsql AS $$ BEGIN IF NOT COALESCE(((NEW.presence_context_token IS '
                'NULL AND NEW.presence_json IS NULL) OR (NEW.presence_context_token IS NOT '
                'NULL AND NEW.presence_json IS NOT NULL AND '
                'octet_length(NEW.presence_json)<=4096 AND '
                "((NEW.presence_json::jsonb->'impressions'->>'presence')!='present' OR "
                "CAST((NEW.presence_json::jsonb->'impressions'->>'value') AS "
                'NUMERIC)=NEW.impressions) AND '
                "((NEW.presence_json::jsonb->'clicks'->>'presence')!='present' OR "
                "CAST((NEW.presence_json::jsonb->'clicks'->>'value') AS NUMERIC)=NEW.clicks) "
                "AND ((NEW.presence_json::jsonb->'spend_micros'->>'presence')!='present' OR "
                "CAST((NEW.presence_json::jsonb->'spend_micros'->>'value') AS "
                'NUMERIC)=NEW.cost_micros) AND '
                "((NEW.presence_json::jsonb->'selected_conversions'->>'presence')!='present' "
                "OR CAST((NEW.presence_json::jsonb->'selected_conversions'->>'value') AS "
                'NUMERIC)=NEW.conversions) AND '
                "((NEW.presence_json::jsonb->'selected_value_micros'->>'presence')!='present' "
                "OR CAST((NEW.presence_json::jsonb->'selected_value_micros'->>'value') AS "
                'NUMERIC)=NEW.conversion_value_micros) AND EXISTS (SELECT 1 FROM '
                'meta_presence_stage_contexts h JOIN campaigns c ON c.account_id=h.account_id '
                'WHERE h.connection_id=NEW.connection_id AND '
                'h.window_token=NEW.presence_context_token AND c.id=NEW.campaign_id AND '
                "CAST(c.platform AS TEXT)='meta_ads' AND "
                "c.external_campaign_id=(NEW.presence_json::jsonb->>'native_campaign_id') AND "
                "NEW.metric_date=(NEW.presence_json::jsonb->>'metric_date')::date AND "
                'NEW.metric_date>=h.starts_on AND NEW.metric_date<=h.ends_on))),false) THEN '
                "RAISE EXCEPTION 'Meta presence binding mismatch'; END IF; RETURN NEW; END; "
                '$$',
                'CREATE TRIGGER meta_staged_metrics_presence_insert BEFORE INSERT ON '
                'meta_staged_metrics FOR EACH ROW EXECUTE FUNCTION '
                'meta_staged_metrics_presence_binding_fn()',
                'CREATE TRIGGER meta_staged_metrics_presence_update BEFORE UPDATE ON '
                'meta_staged_metrics FOR EACH ROW EXECUTE FUNCTION '
                'meta_staged_metrics_presence_binding_fn()'),
 'sqlite': ('\n'
            'CREATE TABLE meta_presence_stage_contexts (\n'
            '\tconnection_id INTEGER NOT NULL, \n'
            '\twindow_token VARCHAR(32) NOT NULL, \n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\taccount_id INTEGER NOT NULL, \n'
            '\tintegration_id INTEGER NOT NULL, \n'
            '\tnative_advertiser_id VARCHAR(32) NOT NULL, \n'
            '\tgeneration INTEGER NOT NULL, \n'
            '\tprivacy_revision INTEGER NOT NULL, \n'
            '\tstarts_on DATE NOT NULL, \n'
            '\tends_on DATE NOT NULL, \n'
            '\tcaptured_at DATETIME NOT NULL, \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tpayload_digest VARCHAR(64) NOT NULL, \n'
            '\tpayload_bytes INTEGER NOT NULL, \n'
            '\tPRIMARY KEY (connection_id), \n'
            '\tFOREIGN KEY(connection_id, workspace_id) REFERENCES meta_connections (id, '
            'workspace_id) ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(account_id, workspace_id, integration_id) REFERENCES '
            'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
            '\tCONSTRAINT uq_meta_presence_token UNIQUE (connection_id, window_token), \n'
            '\tCONSTRAINT ck_meta_presence_revision CHECK (generation > 0 AND '
            'privacy_revision >= 0), \n'
            '\tCONSTRAINT ck_meta_presence_dates CHECK (starts_on <= ends_on), \n'
            '\tCONSTRAINT ck_meta_presence_token_length CHECK (length(window_token) = 32), \n'
            '\tCONSTRAINT ck_meta_presence_bytes CHECK (payload_bytes > 0 AND payload_bytes '
            '<= 8192)\n'
            ')\n'
            '\n',
            '\n'
            'CREATE TABLE meta_staged_metrics_presence_new (\n'
            '\tpresence_context_token VARCHAR(32), \n'
            '\tpresence_json TEXT, \n'
            '\tconnection_id INTEGER NOT NULL, \n'
            '\tcampaign_id INTEGER NOT NULL, \n'
            '\tmetric_date DATE NOT NULL, \n'
            '\timpressions INTEGER NOT NULL, \n'
            '\tclicks INTEGER NOT NULL, \n'
            '\tcost_micros BIGINT NOT NULL, \n'
            '\tconversions NUMERIC(18, 6) NOT NULL, \n'
            '\tconversion_value_micros BIGINT NOT NULL, \n'
            '\tPRIMARY KEY (connection_id, campaign_id, metric_date), \n'
            '\tFOREIGN KEY(connection_id, presence_context_token) REFERENCES '
            'meta_presence_stage_contexts (connection_id, window_token) ON DELETE RESTRICT, \n'
            '\tCONSTRAINT ck_meta_presence_pair CHECK ((presence_context_token IS NULL AND '
            'presence_json IS NULL) OR (presence_context_token IS NOT NULL AND presence_json '
            'IS NOT NULL)), \n'
            '\tFOREIGN KEY(connection_id) REFERENCES meta_connections (id) ON DELETE '
            'CASCADE, \n'
            '\tFOREIGN KEY(campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE\n'
            ')\n'
            '\n',
            'INSERT INTO meta_staged_metrics_presence_new '
            '(connection_id,campaign_id,metric_date,impressions,clicks,cost_micros,conversions,conversion_value_micros) '
            'SELECT '
            'connection_id,campaign_id,metric_date,impressions,clicks,cost_micros,conversions,conversion_value_micros '
            'FROM meta_staged_metrics',
            'DROP TABLE meta_staged_metrics',
            'ALTER TABLE meta_staged_metrics_presence_new RENAME TO meta_staged_metrics',
            'CREATE TRIGGER meta_presence_stage_contexts_presence_insert BEFORE INSERT ON '
            'meta_presence_stage_contexts WHEN NOT '
            'COALESCE((NEW.payload_bytes=length(CAST(NEW.canonical_json AS BLOB)) AND '
            "CAST(json_extract(NEW.canonical_json, '$.window_token') AS "
            'TEXT)=CAST(NEW.window_token AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.workspace_id') AS TEXT)=CAST(NEW.workspace_id AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.account_id') AS "
            'TEXT)=CAST(NEW.account_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.integration_id') AS TEXT)=CAST(NEW.integration_id AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.native_advertiser_id') AS "
            'TEXT)=CAST(NEW.native_advertiser_id AS TEXT) AND '
            "CAST(json_extract(NEW.canonical_json, '$.generation') AS "
            'TEXT)=CAST(NEW.generation AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.privacy_revision') AS TEXT)=CAST(NEW.privacy_revision AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.starts_on') AS TEXT)=CAST(NEW.starts_on "
            "AS TEXT) AND CAST(json_extract(NEW.canonical_json, '$.ends_on') AS "
            'TEXT)=CAST(NEW.ends_on AS TEXT) AND julianday(json_extract(NEW.canonical_json, '
            "'$.captured_at'))=julianday(NEW.captured_at) AND "
            'julianday(NEW.ends_on)-julianday(NEW.starts_on)<400 AND '
            'json_extract(NEW.canonical_json, '
            "'$.schema_version')='inlet.meta-presence-window.v1' AND "
            "CAST(json_extract(NEW.canonical_json, '$.nativeconnection_id') AS "
            'TEXT)=CAST(NEW.connection_id AS TEXT) AND EXISTS (SELECT 1 FROM meta_connections '
            'c JOIN advertising_accounts a ON a.id=c.account_id JOIN workspaces w ON '
            'w.id=c.workspace_id WHERE c.id=NEW.connection_id AND '
            'c.workspace_id=NEW.workspace_id AND c.account_id=NEW.account_id AND '
            'c.workspace_integration_id=NEW.integration_id AND '
            'c.external_account_id=NEW.native_advertiser_id AND c.generation=NEW.generation '
            'AND c.window_start=NEW.starts_on AND c.window_end=NEW.ends_on AND '
            "c.status='connected' AND w.export_privacy_revision=NEW.privacy_revision AND "
            'a.workspace_id=NEW.workspace_id AND a.connection_id=NEW.integration_id AND '
            'a.external_account_id=NEW.native_advertiser_id AND CAST(a.platform AS '
            "TEXT)='meta_ads' AND a.currency_code=json_extract(NEW.canonical_json, "
            "'$.currency') AND a.time_zone=json_extract(NEW.canonical_json, '$.time_zone') "
            'AND ((c.conversion_action_type=json_extract(NEW.canonical_json, '
            "'$.selected_event.native_event_id') AND json_extract(NEW.canonical_json, "
            "'$.selected_event.provenance')='explicit_selected') OR (c.conversion_action_type "
            "IS NULL AND json_extract(NEW.canonical_json, '$.selected_event.native_event_id') "
            'IS NULL AND json_extract(NEW.canonical_json, '
            "'$.selected_event.provenance')='unavailable')))),0) BEGIN SELECT "
            "RAISE(ABORT,'Meta presence binding mismatch'); END",
            'CREATE TRIGGER meta_presence_stage_contexts_immutable BEFORE UPDATE ON '
            "meta_presence_stage_contexts BEGIN SELECT RAISE(ABORT,'immutable Meta presence "
            "context'); END",
            'CREATE TRIGGER meta_staged_metrics_presence_insert BEFORE INSERT ON '
            'meta_staged_metrics WHEN NOT COALESCE(((NEW.presence_context_token IS NULL AND '
            'NEW.presence_json IS NULL) OR (NEW.presence_context_token IS NOT NULL AND '
            'NEW.presence_json IS NOT NULL AND length(CAST(NEW.presence_json AS BLOB))<=4096 '
            "AND (json_extract(NEW.presence_json, '$.impressions.presence')!='present' OR "
            "CAST(json_extract(NEW.presence_json, '$.impressions.value') AS "
            'NUMERIC)=NEW.impressions) AND (json_extract(NEW.presence_json, '
            "'$.clicks.presence')!='present' OR CAST(json_extract(NEW.presence_json, "
            "'$.clicks.value') AS NUMERIC)=NEW.clicks) AND (json_extract(NEW.presence_json, "
            "'$.spend_micros.presence')!='present' OR CAST(json_extract(NEW.presence_json, "
            "'$.spend_micros.value') AS NUMERIC)=NEW.cost_micros) AND "
            "(json_extract(NEW.presence_json, '$.selected_conversions.presence')!='present' "
            "OR CAST(json_extract(NEW.presence_json, '$.selected_conversions.value') AS "
            'NUMERIC)=NEW.conversions) AND (json_extract(NEW.presence_json, '
            "'$.selected_value_micros.presence')!='present' OR "
            "CAST(json_extract(NEW.presence_json, '$.selected_value_micros.value') AS "
            'NUMERIC)=NEW.conversion_value_micros) AND EXISTS (SELECT 1 FROM '
            'meta_presence_stage_contexts h JOIN campaigns c ON c.account_id=h.account_id '
            'WHERE h.connection_id=NEW.connection_id AND '
            'h.window_token=NEW.presence_context_token AND c.id=NEW.campaign_id AND '
            "CAST(c.platform AS TEXT)='meta_ads' AND "
            "c.external_campaign_id=json_extract(NEW.presence_json, '$.native_campaign_id') "
            "AND NEW.metric_date=json_extract(NEW.presence_json, '$.metric_date') AND "
            'NEW.metric_date>=h.starts_on AND NEW.metric_date<=h.ends_on))),0) BEGIN SELECT '
            "RAISE(ABORT,'Meta presence binding mismatch'); END",
            'CREATE TRIGGER meta_staged_metrics_presence_update BEFORE UPDATE ON '
            'meta_staged_metrics WHEN NOT COALESCE(((NEW.presence_context_token IS NULL AND '
            'NEW.presence_json IS NULL) OR (NEW.presence_context_token IS NOT NULL AND '
            'NEW.presence_json IS NOT NULL AND length(CAST(NEW.presence_json AS BLOB))<=4096 '
            "AND (json_extract(NEW.presence_json, '$.impressions.presence')!='present' OR "
            "CAST(json_extract(NEW.presence_json, '$.impressions.value') AS "
            'NUMERIC)=NEW.impressions) AND (json_extract(NEW.presence_json, '
            "'$.clicks.presence')!='present' OR CAST(json_extract(NEW.presence_json, "
            "'$.clicks.value') AS NUMERIC)=NEW.clicks) AND (json_extract(NEW.presence_json, "
            "'$.spend_micros.presence')!='present' OR CAST(json_extract(NEW.presence_json, "
            "'$.spend_micros.value') AS NUMERIC)=NEW.cost_micros) AND "
            "(json_extract(NEW.presence_json, '$.selected_conversions.presence')!='present' "
            "OR CAST(json_extract(NEW.presence_json, '$.selected_conversions.value') AS "
            'NUMERIC)=NEW.conversions) AND (json_extract(NEW.presence_json, '
            "'$.selected_value_micros.presence')!='present' OR "
            "CAST(json_extract(NEW.presence_json, '$.selected_value_micros.value') AS "
            'NUMERIC)=NEW.conversion_value_micros) AND EXISTS (SELECT 1 FROM '
            'meta_presence_stage_contexts h JOIN campaigns c ON c.account_id=h.account_id '
            'WHERE h.connection_id=NEW.connection_id AND '
            'h.window_token=NEW.presence_context_token AND c.id=NEW.campaign_id AND '
            "CAST(c.platform AS TEXT)='meta_ads' AND "
            "c.external_campaign_id=json_extract(NEW.presence_json, '$.native_campaign_id') "
            "AND NEW.metric_date=json_extract(NEW.presence_json, '$.metric_date') AND "
            'NEW.metric_date>=h.starts_on AND NEW.metric_date<=h.ends_on))),0) BEGIN SELECT '
            "RAISE(ABORT,'Meta presence binding mismatch'); END")}

DOWN = {'postgresql': ('DROP TRIGGER meta_staged_metrics_presence_insert ON meta_staged_metrics',
                'DROP TRIGGER meta_staged_metrics_presence_update ON meta_staged_metrics',
                'DROP FUNCTION meta_staged_metrics_presence_binding_fn()',
                'ALTER TABLE meta_staged_metrics DROP CONSTRAINT '
                'fk_meta_staged_presence_context',
                'ALTER TABLE meta_staged_metrics DROP CONSTRAINT ck_meta_presence_pair',
                'ALTER TABLE meta_staged_metrics DROP COLUMN presence_json',
                'ALTER TABLE meta_staged_metrics DROP COLUMN presence_context_token',
                'DROP TABLE meta_presence_stage_contexts',
                'DROP FUNCTION meta_presence_stage_contexts_presence_binding_fn()',
                'DROP FUNCTION meta_presence_stage_contexts_presence_immutable_fn()'),
 'sqlite': ('CREATE TABLE meta_staged_metrics_presence_old (connection_id INTEGER NOT NULL '
            'REFERENCES meta_connections(id) ON DELETE CASCADE, campaign_id INTEGER NOT NULL '
            'REFERENCES campaigns(id) ON DELETE CASCADE, metric_date DATE NOT NULL, '
            'impressions INTEGER NOT NULL, clicks INTEGER NOT NULL, cost_micros BIGINT NOT '
            'NULL, conversions NUMERIC(18,6) NOT NULL, conversion_value_micros BIGINT NOT '
            'NULL, PRIMARY KEY (connection_id,campaign_id,metric_date))',
            'INSERT INTO meta_staged_metrics_presence_old '
            '(connection_id,campaign_id,metric_date,impressions,clicks,cost_micros,conversions,conversion_value_micros) '
            'SELECT '
            'connection_id,campaign_id,metric_date,impressions,clicks,cost_micros,conversions,conversion_value_micros '
            'FROM meta_staged_metrics',
            'DROP TABLE meta_staged_metrics',
            'ALTER TABLE meta_staged_metrics_presence_old RENAME TO meta_staged_metrics',
            'DROP TABLE meta_presence_stage_contexts')}
