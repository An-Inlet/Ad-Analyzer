# ruff: noqa: E501
"""Owned immutable selected reporting; no public confirmation authority."""

import sqlalchemy as sa
from alembic import op

revision = "20261011_0091"
down_revision = "20261008_0090"
branch_labels = None
depends_on = None
TABLES = (
    "customer_event_selections",
    "customer_event_selection_current",
    "selected_reporting_captures",
    "selected_reporting_facts",
)


def upgrade() -> None:
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    db = op.get_bind()
    if any(db.scalar(sa.text(f"SELECT EXISTS(SELECT 1 FROM {name})")) for name in TABLES):
        raise RuntimeError("cannot discard retained selected reporting")
    for name in reversed(TABLES):
        op.drop_table(name)
        if db.dialect.name == "postgresql":
            for kind in ("binding", "immutable", "guard", "erase", "invalidate"):
                op.execute(f"DROP FUNCTION IF EXISTS {name}_{kind}_fn()")


# Frozen DDL: no mutable application imports.
SQL = {'postgresql': ('\n'
                'CREATE TABLE customer_event_selections (\n'
                '\tid VARCHAR(32) NOT NULL, \n'
                '\tconfirmed_by_customer_id VARCHAR(32) NOT NULL, \n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\taccount_id INTEGER NOT NULL, \n'
                '\tconnection_id INTEGER NOT NULL, \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tpayload_digest VARCHAR(64) NOT NULL, \n'
                '\tpayload_bytes INTEGER NOT NULL, \n'
                '\tPRIMARY KEY (id), \n'
                '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
                'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
                '\tCONSTRAINT uq_selected_selection_scope UNIQUE (id, account_id, workspace_id, '
                'payload_digest), \n'
                '\tFOREIGN KEY(confirmed_by_customer_id) REFERENCES customer_users (id) ON DELETE '
                'CASCADE, \n'
                '\tCONSTRAINT ck_selection_bytes CHECK (payload_bytes > 0 AND payload_bytes <= '
                '8192)\n'
                ')\n'
                '\n',
                'CREATE FUNCTION customer_event_selections_binding_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN IF NOT '
                'COALESCE((NEW.payload_bytes=octet_length(NEW.canonical_json) AND EXISTS (SELECT 1 '
                'FROM customer_memberships m JOIN customer_users u ON u.id=m.user_id WHERE '
                'm.workspace_id=NEW.workspace_id AND m.user_id=NEW.confirmed_by_customer_id AND '
                "m.status='active' AND m.role='owner' AND u.status='active') AND "
                '(NEW.canonical_json::jsonb #>> '
                "'{schema_version}')='inlet.customer-event-selection.v1' AND "
                "CAST((NEW.canonical_json::jsonb #>> '{selection_id}') AS TEXT)=CAST(NEW.id AS "
                "TEXT) AND CAST((NEW.canonical_json::jsonb #>> '{scope,workspace_id}') AS "
                'TEXT)=CAST(NEW.workspace_id AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> '
                "'{scope,account_id}') AS TEXT)=CAST(NEW.account_id AS TEXT) AND "
                "CAST((NEW.canonical_json::jsonb #>> '{scope,connection_id}') AS "
                'TEXT)=CAST(NEW.connection_id AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> '
                "'{confirmed_by_customer_id}') AS TEXT)=CAST(NEW.confirmed_by_customer_id AS "
                "TEXT)),false) THEN RAISE EXCEPTION 'selected binding mismatch'; END IF; RETURN "
                'NEW; END; $$',
                'CREATE TRIGGER customer_event_selections_binding BEFORE INSERT ON '
                'customer_event_selections FOR EACH ROW EXECUTE FUNCTION '
                'customer_event_selections_binding_fn()',
                'CREATE FUNCTION customer_event_selections_immutable_fn() RETURNS trigger LANGUAGE '
                "plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable selected reporting'; END; $$",
                'CREATE TRIGGER customer_event_selections_immutable BEFORE UPDATE ON '
                'customer_event_selections FOR EACH ROW EXECUTE FUNCTION '
                'customer_event_selections_immutable_fn()',
                'CREATE FUNCTION customer_event_selections_guard_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR '
                'UPDATE NOWAIT; RETURN OLD; END; $$',
                'CREATE TRIGGER customer_event_selections_guard BEFORE DELETE ON '
                'customer_event_selections FOR EACH ROW EXECUTE FUNCTION '
                'customer_event_selections_guard_fn()',
                'CREATE FUNCTION customer_event_selections_erase_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN DELETE FROM initial_calibration_runs WHERE '
                'workspace_id=OLD.workspace_id AND account_id=OLD.account_id;UPDATE workspaces SET '
                'export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id; '
                'RETURN NULL; END; $$',
                'CREATE TRIGGER customer_event_selections_erase AFTER DELETE ON '
                'customer_event_selections FOR EACH ROW EXECUTE FUNCTION '
                'customer_event_selections_erase_fn()',
                '\n'
                'CREATE TABLE customer_event_selection_current (\n'
                '\tinvalidated BOOLEAN DEFAULT false NOT NULL, \n'
                '\taccount_id INTEGER NOT NULL, \n'
                '\tselection_id VARCHAR(32) NOT NULL, \n'
                '\tselection_digest VARCHAR(64) NOT NULL, \n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\tconnection_id INTEGER NOT NULL, \n'
                '\tPRIMARY KEY (account_id), \n'
                '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
                'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(selection_id, account_id, workspace_id, selection_digest) '
                'REFERENCES customer_event_selections (id, account_id, workspace_id, '
                'payload_digest) ON DELETE CASCADE\n'
                ')\n'
                '\n',
                'CREATE FUNCTION customer_event_selection_current_invalidate_fn() RETURNS trigger '
                'LANGUAGE plpgsql AS $$ BEGIN IF NOT OLD.invalidated AND NEW.invalidated THEN '
                'DELETE FROM selected_reporting_captures WHERE workspace_id=NEW.workspace_id AND '
                'account_id=NEW.account_id; DELETE FROM initial_calibration_runs WHERE '
                'workspace_id=NEW.workspace_id AND account_id=NEW.account_id; UPDATE workspaces '
                'SET export_privacy_revision=export_privacy_revision+1 WHERE id=NEW.workspace_id; '
                'END IF; RETURN NEW; END; $$',
                'CREATE TRIGGER customer_event_selection_current_invalidate AFTER UPDATE ON '
                'customer_event_selection_current FOR EACH ROW EXECUTE FUNCTION '
                'customer_event_selection_current_invalidate_fn()',
                'CREATE FUNCTION customer_event_selection_current_binding_fn() RETURNS trigger '
                'LANGUAGE plpgsql AS $$ BEGIN IF NOT COALESCE((EXISTS (SELECT 1 FROM '
                'customer_event_selections s WHERE s.id=NEW.selection_id AND '
                's.payload_digest=NEW.selection_digest AND s.account_id=NEW.account_id AND '
                's.workspace_id=NEW.workspace_id AND s.connection_id=NEW.connection_id) AND NOT '
                'NEW.invalidated AND EXISTS(SELECT 1 FROM customer_event_selections s JOIN '
                'advertising_accounts a ON a.id=s.account_id AND a.workspace_id=s.workspace_id '
                'JOIN workspaces w ON w.id=s.workspace_id JOIN workspace_integrations i ON '
                'i.id=a.connection_id AND i.workspace_id=a.workspace_id WHERE '
                's.id=NEW.selection_id AND s.payload_digest=NEW.selection_digest AND '
                's.account_id=NEW.account_id AND s.workspace_id=NEW.workspace_id AND '
                "s.connection_id=NEW.connection_id AND w.status='active' AND i.status='active' AND "
                'i.provider=CAST(a.platform AS TEXT) AND CAST((s.canonical_json::jsonb #>> '
                "'{scope,privacy_revision}') AS TEXT)=CAST(w.export_privacy_revision AS TEXT) AND "
                "CAST((s.canonical_json::jsonb #>> '{scope,connection_id}') AS "
                'TEXT)=CAST(a.connection_id AS TEXT) AND CAST((s.canonical_json::jsonb #>> '
                "'{scope,native_account_id}') AS TEXT)=CAST(a.external_account_id AS TEXT) AND "
                "CAST((s.canonical_json::jsonb #>> '{scope,platform}') AS TEXT)=CAST(a.platform AS "
                "TEXT) AND CAST((s.canonical_json::jsonb #>> '{scope,currency}') AS "
                'TEXT)=CAST(a.currency_code AS TEXT) AND CAST((s.canonical_json::jsonb #>> '
                "'{scope,time_zone}') AS TEXT)=CAST(a.time_zone AS TEXT) AND ((CAST(a.platform AS "
                "TEXT)='meta_ads' AND EXISTS(SELECT 1 FROM meta_connections n WHERE "
                'n.workspace_id=a.workspace_id AND n.account_id=a.id AND CAST(n.id AS '
                "TEXT)=(s.canonical_json::jsonb #>> '{scope,source_connection_ref}') AND "
                'CAST(n.generation AS TEXT)=CAST((s.canonical_json::jsonb #>> '
                "'{scope,generation}') AS TEXT) AND n.status='connected' AND n.error_code IS NULL "
                'AND n.workspace_integration_id=a.connection_id AND '
                'n.external_account_id=a.external_account_id)) OR (CAST(a.platform AS '
                "TEXT)='google_ads' AND EXISTS(SELECT 1 FROM google_customer_connections n WHERE "
                'n.workspace_id=a.workspace_id AND n.account_id=a.id AND CAST(n.id AS '
                "TEXT)=(s.canonical_json::jsonb #>> '{scope,source_connection_ref}') AND "
                'CAST(n.generation AS TEXT)=CAST((s.canonical_json::jsonb #>> '
                "'{scope,generation}') AS TEXT) AND n.status='connected' AND n.error_code IS NULL "
                'AND n.integration_id=a.connection_id AND '
                'n.external_account_id=a.external_account_id)) OR (CAST(a.platform AS '
                "TEXT)='tiktok_ads' AND EXISTS(SELECT 1 FROM customer_source_connections n WHERE "
                'n.workspace_id=a.workspace_id AND n.account_id=a.id AND CAST(n.id AS '
                "TEXT)=(s.canonical_json::jsonb #>> '{scope,source_connection_ref}') AND "
                'CAST(n.generation AS TEXT)=CAST((s.canonical_json::jsonb #>> '
                "'{scope,generation}') AS TEXT) AND n.status='connected' AND n.error_code IS NULL "
                'AND n.integration_id=a.connection_id AND n.external_id=a.external_account_id AND '
                "n.provider='tiktok_ads'))))),false) THEN RAISE EXCEPTION 'selected binding "
                "mismatch'; END IF; RETURN NEW; END; $$",
                'CREATE TRIGGER customer_event_selection_current_binding BEFORE INSERT ON '
                'customer_event_selection_current FOR EACH ROW EXECUTE FUNCTION '
                'customer_event_selection_current_binding_fn()',
                'CREATE FUNCTION customer_event_selection_current_immutable_fn() RETURNS trigger '
                'LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id '
                'FOR UPDATE NOWAIT; IF NOT COALESCE(((NEW.account_id=OLD.account_id AND '
                'NEW.workspace_id=OLD.workspace_id AND NEW.connection_id=OLD.connection_id) AND '
                '((NEW.selection_id=OLD.selection_id AND NEW.selection_digest=OLD.selection_digest '
                'AND NEW.invalidated=OLD.invalidated) OR (NEW.selection_id=OLD.selection_id AND '
                'NEW.selection_digest=OLD.selection_digest AND NOT OLD.invalidated AND '
                'NEW.invalidated) OR (OLD.invalidated AND NOT NEW.invalidated AND '
                'NEW.selection_id<>OLD.selection_id AND EXISTS(SELECT 1 FROM '
                'customer_event_selections s JOIN advertising_accounts a ON a.id=s.account_id AND '
                'a.workspace_id=s.workspace_id JOIN workspaces w ON w.id=s.workspace_id JOIN '
                'workspace_integrations i ON i.id=a.connection_id AND '
                'i.workspace_id=a.workspace_id WHERE s.id=NEW.selection_id AND '
                's.payload_digest=NEW.selection_digest AND s.account_id=NEW.account_id AND '
                's.workspace_id=NEW.workspace_id AND s.connection_id=NEW.connection_id AND '
                "w.status='active' AND i.status='active' AND i.provider=CAST(a.platform AS TEXT) "
                "AND CAST((s.canonical_json::jsonb #>> '{scope,privacy_revision}') AS "
                'TEXT)=CAST(w.export_privacy_revision AS TEXT) AND CAST((s.canonical_json::jsonb '
                "#>> '{scope,connection_id}') AS TEXT)=CAST(a.connection_id AS TEXT) AND "
                "CAST((s.canonical_json::jsonb #>> '{scope,native_account_id}') AS "
                'TEXT)=CAST(a.external_account_id AS TEXT) AND CAST((s.canonical_json::jsonb #>> '
                "'{scope,platform}') AS TEXT)=CAST(a.platform AS TEXT) AND "
                "CAST((s.canonical_json::jsonb #>> '{scope,currency}') AS "
                'TEXT)=CAST(a.currency_code AS TEXT) AND CAST((s.canonical_json::jsonb #>> '
                "'{scope,time_zone}') AS TEXT)=CAST(a.time_zone AS TEXT) AND ((CAST(a.platform AS "
                "TEXT)='meta_ads' AND EXISTS(SELECT 1 FROM meta_connections n WHERE "
                'n.workspace_id=a.workspace_id AND n.account_id=a.id AND CAST(n.id AS '
                "TEXT)=(s.canonical_json::jsonb #>> '{scope,source_connection_ref}') AND "
                'CAST(n.generation AS TEXT)=CAST((s.canonical_json::jsonb #>> '
                "'{scope,generation}') AS TEXT) AND n.status='connected' AND n.error_code IS NULL "
                'AND n.workspace_integration_id=a.connection_id AND '
                'n.external_account_id=a.external_account_id)) OR (CAST(a.platform AS '
                "TEXT)='google_ads' AND EXISTS(SELECT 1 FROM google_customer_connections n WHERE "
                'n.workspace_id=a.workspace_id AND n.account_id=a.id AND CAST(n.id AS '
                "TEXT)=(s.canonical_json::jsonb #>> '{scope,source_connection_ref}') AND "
                'CAST(n.generation AS TEXT)=CAST((s.canonical_json::jsonb #>> '
                "'{scope,generation}') AS TEXT) AND n.status='connected' AND n.error_code IS NULL "
                'AND n.integration_id=a.connection_id AND '
                'n.external_account_id=a.external_account_id)) OR (CAST(a.platform AS '
                "TEXT)='tiktok_ads' AND EXISTS(SELECT 1 FROM customer_source_connections n WHERE "
                'n.workspace_id=a.workspace_id AND n.account_id=a.id AND CAST(n.id AS '
                "TEXT)=(s.canonical_json::jsonb #>> '{scope,source_connection_ref}') AND "
                'CAST(n.generation AS TEXT)=CAST((s.canonical_json::jsonb #>> '
                "'{scope,generation}') AS TEXT) AND n.status='connected' AND n.error_code IS NULL "
                'AND n.integration_id=a.connection_id AND n.external_id=a.external_account_id AND '
                "n.provider='tiktok_ads'))))))),false) THEN RAISE EXCEPTION 'immutable selected "
                "reporting'; END IF; RETURN NEW; END; $$",
                'CREATE TRIGGER customer_event_selection_current_immutable BEFORE UPDATE ON '
                'customer_event_selection_current FOR EACH ROW EXECUTE FUNCTION '
                'customer_event_selection_current_immutable_fn()',
                'CREATE FUNCTION customer_event_selection_current_guard_fn() RETURNS trigger '
                'LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id '
                'FOR UPDATE NOWAIT; RETURN OLD; END; $$',
                'CREATE TRIGGER customer_event_selection_current_guard BEFORE DELETE ON '
                'customer_event_selection_current FOR EACH ROW EXECUTE FUNCTION '
                'customer_event_selection_current_guard_fn()',
                'CREATE FUNCTION customer_event_selection_current_erase_fn() RETURNS trigger '
                'LANGUAGE plpgsql AS $$ BEGIN DELETE FROM selected_reporting_captures WHERE '
                'workspace_id=OLD.workspace_id AND account_id=OLD.account_id;DELETE FROM '
                'initial_calibration_runs WHERE workspace_id=OLD.workspace_id AND '
                'account_id=OLD.account_id;UPDATE workspaces SET '
                'export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id; '
                'RETURN NULL; END; $$',
                'CREATE TRIGGER customer_event_selection_current_erase AFTER DELETE ON '
                'customer_event_selection_current FOR EACH ROW EXECUTE FUNCTION '
                'customer_event_selection_current_erase_fn()',
                '\n'
                'CREATE TABLE selected_reporting_captures (\n'
                '\tid VARCHAR(32) NOT NULL, \n'
                '\tselection_id VARCHAR(32) NOT NULL, \n'
                '\tselection_digest VARCHAR(64) NOT NULL, \n'
                '\tcompletion_id VARCHAR(32) NOT NULL, \n'
                '\trequest_digest VARCHAR(64) NOT NULL, \n'
                '\tfact_count INTEGER NOT NULL, \n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\taccount_id INTEGER NOT NULL, \n'
                '\tconnection_id INTEGER NOT NULL, \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tpayload_digest VARCHAR(64) NOT NULL, \n'
                '\tpayload_bytes INTEGER NOT NULL, \n'
                '\tPRIMARY KEY (id), \n'
                '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
                'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
                '\tCONSTRAINT uq_selected_capture_scope UNIQUE (id, account_id, workspace_id), \n'
                '\tFOREIGN KEY(selection_id, account_id, workspace_id, selection_digest) '
                'REFERENCES customer_event_selections (id, account_id, workspace_id, '
                'payload_digest) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(completion_id, account_id, workspace_id) REFERENCES '
                'campaign_performance_completions (id, account_id, workspace_id) ON DELETE '
                'CASCADE, \n'
                '\tCONSTRAINT ck_selected_count CHECK (fact_count >= 0 AND fact_count <= 50000), \n'
                '\tCONSTRAINT ck_selected_header_bytes CHECK (payload_bytes > 0 AND payload_bytes '
                '<= 16384)\n'
                ')\n'
                '\n',
                'CREATE FUNCTION selected_reporting_captures_binding_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN IF NOT '
                'COALESCE((NEW.payload_bytes=octet_length(NEW.canonical_json) AND EXISTS (SELECT 1 '
                'FROM customer_event_selections s WHERE s.id=NEW.selection_id AND '
                's.connection_id=NEW.connection_id AND s.workspace_id=NEW.workspace_id AND '
                's.account_id=NEW.account_id) AND (NEW.canonical_json::jsonb #>> '
                "'{schema_version}')='inlet.selected-capture.v1' AND "
                "CAST((NEW.canonical_json::jsonb #>> '{request,capture_id}') AS TEXT)=CAST(NEW.id "
                'AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> '
                "'{request,aggregate,scope,workspace_id}') AS TEXT)=CAST(NEW.workspace_id AS TEXT) "
                "AND CAST((NEW.canonical_json::jsonb #>> '{request,aggregate,scope,account_id}') "
                'AS TEXT)=CAST(NEW.account_id AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> '
                "'{request,aggregate,scope,connection_id}') AS TEXT)=CAST(NEW.connection_id AS "
                "TEXT) AND CAST((NEW.canonical_json::jsonb #>> '{request,selection,selection_id}') "
                'AS TEXT)=CAST(NEW.selection_id AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> '
                "'{request,selection_digest}') AS TEXT)=CAST(NEW.selection_digest AS TEXT) AND "
                "CAST((NEW.canonical_json::jsonb #>> '{request,aggregate,completion_id}') AS "
                'TEXT)=CAST(NEW.completion_id AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> '
                "'{request_digest}') AS TEXT)=CAST(NEW.request_digest AS TEXT)),false) THEN RAISE "
                "EXCEPTION 'selected binding mismatch'; END IF; RETURN NEW; END; $$",
                'CREATE TRIGGER selected_reporting_captures_binding BEFORE INSERT ON '
                'selected_reporting_captures FOR EACH ROW EXECUTE FUNCTION '
                'selected_reporting_captures_binding_fn()',
                'CREATE FUNCTION selected_reporting_captures_immutable_fn() RETURNS trigger '
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable selected reporting'; END; "
                '$$',
                'CREATE TRIGGER selected_reporting_captures_immutable BEFORE UPDATE ON '
                'selected_reporting_captures FOR EACH ROW EXECUTE FUNCTION '
                'selected_reporting_captures_immutable_fn()',
                'CREATE FUNCTION selected_reporting_captures_guard_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR '
                'UPDATE NOWAIT; RETURN OLD; END; $$',
                'CREATE TRIGGER selected_reporting_captures_guard BEFORE DELETE ON '
                'selected_reporting_captures FOR EACH ROW EXECUTE FUNCTION '
                'selected_reporting_captures_guard_fn()',
                'CREATE FUNCTION selected_reporting_captures_erase_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN DELETE FROM initial_calibration_runs WHERE '
                'workspace_id=OLD.workspace_id AND account_id=OLD.account_id;UPDATE workspaces SET '
                'export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id; '
                'RETURN NULL; END; $$',
                'CREATE TRIGGER selected_reporting_captures_erase AFTER DELETE ON '
                'selected_reporting_captures FOR EACH ROW EXECUTE FUNCTION '
                'selected_reporting_captures_erase_fn()',
                '\n'
                'CREATE TABLE selected_reporting_facts (\n'
                '\tcapture_id VARCHAR(32) NOT NULL, \n'
                '\tcampaign_id INTEGER NOT NULL, \n'
                '\tmetric_date DATE NOT NULL, \n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\taccount_id INTEGER NOT NULL, \n'
                '\tnative_campaign_id VARCHAR(32) NOT NULL, \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tpayload_digest VARCHAR(64) NOT NULL, \n'
                '\tpayload_bytes INTEGER NOT NULL, \n'
                '\tPRIMARY KEY (capture_id, campaign_id, metric_date), \n'
                '\tFOREIGN KEY(capture_id, account_id, workspace_id) REFERENCES '
                'selected_reporting_captures (id, account_id, workspace_id) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(campaign_id, account_id) REFERENCES campaigns (id, account_id) ON '
                'DELETE CASCADE, \n'
                '\tCONSTRAINT uq_selected_native_day UNIQUE (capture_id, native_campaign_id, '
                'metric_date), \n'
                '\tCONSTRAINT ck_selected_fact_bytes CHECK (payload_bytes > 0 AND payload_bytes <= '
                '4096)\n'
                ')\n'
                '\n',
                'CREATE FUNCTION selected_reporting_facts_binding_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN IF NOT '
                'COALESCE((NEW.payload_bytes=octet_length(NEW.canonical_json) AND EXISTS (SELECT 1 '
                'FROM campaigns c JOIN selected_reporting_captures h ON h.id=NEW.capture_id WHERE '
                'c.id=NEW.campaign_id AND c.account_id=NEW.account_id AND '
                'c.external_campaign_id=NEW.native_campaign_id AND h.workspace_id=NEW.workspace_id '
                'AND h.account_id=NEW.account_id) AND EXISTS(SELECT 1 FROM '
                'selected_reporting_captures h JOIN campaigns c ON c.id=NEW.campaign_id AND '
                'c.account_id=NEW.account_id WHERE h.id=NEW.capture_id AND CAST(c.platform AS '
                "TEXT)=(h.canonical_json::jsonb #>> '{request,aggregate,scope,platform}')) AND "
                '(NEW.canonical_json::jsonb #>> '
                "'{schema_version}')='inlet.selected-campaign-day.v1' AND "
                "CAST((NEW.canonical_json::jsonb #>> '{capture_id}') AS TEXT)=CAST(NEW.capture_id "
                "AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> '{campaign_id}') AS "
                'TEXT)=CAST(NEW.campaign_id AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> '
                "'{metric_date}') AS TEXT)=CAST(NEW.metric_date AS TEXT) AND "
                "CAST((NEW.canonical_json::jsonb #>> '{native_campaign_id}') AS "
                "TEXT)=CAST(NEW.native_campaign_id AS TEXT)),false) THEN RAISE EXCEPTION 'selected "
                "binding mismatch'; END IF; RETURN NEW; END; $$",
                'CREATE TRIGGER selected_reporting_facts_binding BEFORE INSERT ON '
                'selected_reporting_facts FOR EACH ROW EXECUTE FUNCTION '
                'selected_reporting_facts_binding_fn()',
                'CREATE FUNCTION selected_reporting_facts_immutable_fn() RETURNS trigger LANGUAGE '
                "plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable selected reporting'; END; $$",
                'CREATE TRIGGER selected_reporting_facts_immutable BEFORE UPDATE ON '
                'selected_reporting_facts FOR EACH ROW EXECUTE FUNCTION '
                'selected_reporting_facts_immutable_fn()',
                'CREATE FUNCTION selected_reporting_facts_guard_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR '
                'UPDATE NOWAIT; RETURN OLD; END; $$',
                'CREATE TRIGGER selected_reporting_facts_guard BEFORE DELETE ON '
                'selected_reporting_facts FOR EACH ROW EXECUTE FUNCTION '
                'selected_reporting_facts_guard_fn()',
                'CREATE FUNCTION selected_reporting_facts_erase_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN DELETE FROM selected_reporting_captures WHERE '
                'id=OLD.capture_id AND workspace_id=OLD.workspace_id;DELETE FROM '
                'initial_calibration_runs WHERE workspace_id=OLD.workspace_id AND '
                'account_id=OLD.account_id;UPDATE workspaces SET '
                'export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id; '
                'RETURN NULL; END; $$',
                'CREATE TRIGGER selected_reporting_facts_erase AFTER DELETE ON '
                'selected_reporting_facts FOR EACH ROW EXECUTE FUNCTION '
                'selected_reporting_facts_erase_fn()'),
 'sqlite': ('\n'
            'CREATE TABLE customer_event_selections (\n'
            '\tid VARCHAR(32) NOT NULL, \n'
            '\tconfirmed_by_customer_id VARCHAR(32) NOT NULL, \n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\taccount_id INTEGER NOT NULL, \n'
            '\tconnection_id INTEGER NOT NULL, \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tpayload_digest VARCHAR(64) NOT NULL, \n'
            '\tpayload_bytes INTEGER NOT NULL, \n'
            '\tPRIMARY KEY (id), \n'
            '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
            'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
            '\tCONSTRAINT uq_selected_selection_scope UNIQUE (id, account_id, workspace_id, '
            'payload_digest), \n'
            '\tFOREIGN KEY(confirmed_by_customer_id) REFERENCES customer_users (id) ON DELETE '
            'CASCADE, \n'
            '\tCONSTRAINT ck_selection_bytes CHECK (payload_bytes > 0 AND payload_bytes <= 8192)\n'
            ')\n'
            '\n',
            'CREATE TRIGGER customer_event_selections_binding BEFORE INSERT ON '
            'customer_event_selections WHEN NOT '
            'COALESCE((NEW.payload_bytes=length(CAST(NEW.canonical_json AS BLOB)) AND EXISTS '
            '(SELECT 1 FROM customer_memberships m JOIN customer_users u ON u.id=m.user_id WHERE '
            'm.workspace_id=NEW.workspace_id AND m.user_id=NEW.confirmed_by_customer_id AND '
            "m.status='active' AND m.role='owner' AND u.status='active') AND "
            'json_extract(NEW.canonical_json, '
            "'$.schema_version')='inlet.customer-event-selection.v1' AND "
            "CAST(json_extract(NEW.canonical_json, '$.selection_id') AS TEXT)=CAST(NEW.id AS TEXT) "
            "AND CAST(json_extract(NEW.canonical_json, '$.scope.workspace_id') AS "
            'TEXT)=CAST(NEW.workspace_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.scope.account_id') AS TEXT)=CAST(NEW.account_id AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.scope.connection_id') AS "
            'TEXT)=CAST(NEW.connection_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.confirmed_by_customer_id') AS TEXT)=CAST(NEW.confirmed_by_customer_id AS TEXT) AND "
            '(SELECT foreign_keys FROM pragma_foreign_keys)=1),0) BEGIN SELECT '
            "RAISE(ABORT,'selected binding mismatch'); END",
            'CREATE TRIGGER customer_event_selections_immutable BEFORE UPDATE ON '
            "customer_event_selections BEGIN SELECT RAISE(ABORT,'immutable selected reporting'); "
            'END',
            'CREATE TRIGGER customer_event_selections_erase AFTER DELETE ON '
            'customer_event_selections BEGIN DELETE FROM initial_calibration_runs WHERE '
            'workspace_id=OLD.workspace_id AND account_id=OLD.account_id;UPDATE workspaces SET '
            'export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id; END',
            '\n'
            'CREATE TABLE customer_event_selection_current (\n'
            '\tinvalidated BOOLEAN DEFAULT 0 NOT NULL, \n'
            '\taccount_id INTEGER NOT NULL, \n'
            '\tselection_id VARCHAR(32) NOT NULL, \n'
            '\tselection_digest VARCHAR(64) NOT NULL, \n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\tconnection_id INTEGER NOT NULL, \n'
            '\tPRIMARY KEY (account_id), \n'
            '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
            'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(selection_id, account_id, workspace_id, selection_digest) REFERENCES '
            'customer_event_selections (id, account_id, workspace_id, payload_digest) ON DELETE '
            'CASCADE, \n'
            '\tCONSTRAINT ck_selected_head_boolean CHECK (invalidated IN (0, 1))\n'
            ')\n'
            '\n',
            'CREATE TRIGGER customer_event_selection_current_invalidate AFTER UPDATE ON '
            'customer_event_selection_current WHEN NOT OLD.invalidated AND NEW.invalidated BEGIN '
            'DELETE FROM selected_reporting_captures WHERE workspace_id=NEW.workspace_id AND '
            'account_id=NEW.account_id; DELETE FROM initial_calibration_runs WHERE '
            'workspace_id=NEW.workspace_id AND account_id=NEW.account_id; UPDATE workspaces SET '
            'export_privacy_revision=export_privacy_revision+1 WHERE id=NEW.workspace_id; END',
            'CREATE TRIGGER customer_event_selection_current_binding BEFORE INSERT ON '
            'customer_event_selection_current WHEN NOT COALESCE((EXISTS (SELECT 1 FROM '
            'customer_event_selections s WHERE s.id=NEW.selection_id AND '
            's.payload_digest=NEW.selection_digest AND s.account_id=NEW.account_id AND '
            's.workspace_id=NEW.workspace_id AND s.connection_id=NEW.connection_id) AND NOT '
            'NEW.invalidated AND EXISTS(SELECT 1 FROM customer_event_selections s JOIN '
            'advertising_accounts a ON a.id=s.account_id AND a.workspace_id=s.workspace_id JOIN '
            'workspaces w ON w.id=s.workspace_id JOIN workspace_integrations i ON '
            'i.id=a.connection_id AND i.workspace_id=a.workspace_id WHERE s.id=NEW.selection_id '
            'AND s.payload_digest=NEW.selection_digest AND s.account_id=NEW.account_id AND '
            's.workspace_id=NEW.workspace_id AND s.connection_id=NEW.connection_id AND '
            "w.status='active' AND i.status='active' AND i.provider=CAST(a.platform AS TEXT) AND "
            "CAST(json_extract(s.canonical_json,'$.scope.privacy_revision') AS "
            'TEXT)=CAST(w.export_privacy_revision AS TEXT) AND '
            "CAST(json_extract(s.canonical_json,'$.scope.connection_id') AS "
            'TEXT)=CAST(a.connection_id AS TEXT) AND '
            "CAST(json_extract(s.canonical_json,'$.scope.native_account_id') AS "
            'TEXT)=CAST(a.external_account_id AS TEXT) AND '
            "CAST(json_extract(s.canonical_json,'$.scope.platform') AS TEXT)=CAST(a.platform AS "
            "TEXT) AND CAST(json_extract(s.canonical_json,'$.scope.currency') AS "
            'TEXT)=CAST(a.currency_code AS TEXT) AND '
            "CAST(json_extract(s.canonical_json,'$.scope.time_zone') AS TEXT)=CAST(a.time_zone AS "
            "TEXT) AND ((CAST(a.platform AS TEXT)='meta_ads' AND EXISTS(SELECT 1 FROM "
            'meta_connections n WHERE n.workspace_id=a.workspace_id AND n.account_id=a.id AND '
            "CAST(n.id AS TEXT)=json_extract(s.canonical_json,'$.scope.source_connection_ref') AND "
            "CAST(n.generation AS TEXT)=CAST(json_extract(s.canonical_json,'$.scope.generation') "
            "AS TEXT) AND n.status='connected' AND n.error_code IS NULL AND "
            'n.workspace_integration_id=a.connection_id AND '
            'n.external_account_id=a.external_account_id)) OR (CAST(a.platform AS '
            "TEXT)='google_ads' AND EXISTS(SELECT 1 FROM google_customer_connections n WHERE "
            'n.workspace_id=a.workspace_id AND n.account_id=a.id AND CAST(n.id AS '
            "TEXT)=json_extract(s.canonical_json,'$.scope.source_connection_ref') AND "
            "CAST(n.generation AS TEXT)=CAST(json_extract(s.canonical_json,'$.scope.generation') "
            "AS TEXT) AND n.status='connected' AND n.error_code IS NULL AND "
            'n.integration_id=a.connection_id AND n.external_account_id=a.external_account_id)) OR '
            "(CAST(a.platform AS TEXT)='tiktok_ads' AND EXISTS(SELECT 1 FROM "
            'customer_source_connections n WHERE n.workspace_id=a.workspace_id AND '
            'n.account_id=a.id AND CAST(n.id AS '
            "TEXT)=json_extract(s.canonical_json,'$.scope.source_connection_ref') AND "
            "CAST(n.generation AS TEXT)=CAST(json_extract(s.canonical_json,'$.scope.generation') "
            "AS TEXT) AND n.status='connected' AND n.error_code IS NULL AND "
            'n.integration_id=a.connection_id AND n.external_id=a.external_account_id AND '
            "n.provider='tiktok_ads')))) AND (SELECT foreign_keys FROM pragma_foreign_keys)=1),0) "
            "BEGIN SELECT RAISE(ABORT,'selected binding mismatch'); END",
            'CREATE TRIGGER customer_event_selection_current_immutable BEFORE UPDATE ON '
            'customer_event_selection_current WHEN NOT COALESCE(((NEW.account_id=OLD.account_id '
            'AND NEW.workspace_id=OLD.workspace_id AND NEW.connection_id=OLD.connection_id) AND '
            '((NEW.selection_id=OLD.selection_id AND NEW.selection_digest=OLD.selection_digest AND '
            'NEW.invalidated=OLD.invalidated) OR (NEW.selection_id=OLD.selection_id AND '
            'NEW.selection_digest=OLD.selection_digest AND NOT OLD.invalidated AND '
            'NEW.invalidated) OR (OLD.invalidated AND NOT NEW.invalidated AND '
            'NEW.selection_id<>OLD.selection_id AND EXISTS(SELECT 1 FROM customer_event_selections '
            's JOIN advertising_accounts a ON a.id=s.account_id AND a.workspace_id=s.workspace_id '
            'JOIN workspaces w ON w.id=s.workspace_id JOIN workspace_integrations i ON '
            'i.id=a.connection_id AND i.workspace_id=a.workspace_id WHERE s.id=NEW.selection_id '
            'AND s.payload_digest=NEW.selection_digest AND s.account_id=NEW.account_id AND '
            's.workspace_id=NEW.workspace_id AND s.connection_id=NEW.connection_id AND '
            "w.status='active' AND i.status='active' AND i.provider=CAST(a.platform AS TEXT) AND "
            "CAST(json_extract(s.canonical_json,'$.scope.privacy_revision') AS "
            'TEXT)=CAST(w.export_privacy_revision AS TEXT) AND '
            "CAST(json_extract(s.canonical_json,'$.scope.connection_id') AS "
            'TEXT)=CAST(a.connection_id AS TEXT) AND '
            "CAST(json_extract(s.canonical_json,'$.scope.native_account_id') AS "
            'TEXT)=CAST(a.external_account_id AS TEXT) AND '
            "CAST(json_extract(s.canonical_json,'$.scope.platform') AS TEXT)=CAST(a.platform AS "
            "TEXT) AND CAST(json_extract(s.canonical_json,'$.scope.currency') AS "
            'TEXT)=CAST(a.currency_code AS TEXT) AND '
            "CAST(json_extract(s.canonical_json,'$.scope.time_zone') AS TEXT)=CAST(a.time_zone AS "
            "TEXT) AND ((CAST(a.platform AS TEXT)='meta_ads' AND EXISTS(SELECT 1 FROM "
            'meta_connections n WHERE n.workspace_id=a.workspace_id AND n.account_id=a.id AND '
            "CAST(n.id AS TEXT)=json_extract(s.canonical_json,'$.scope.source_connection_ref') AND "
            "CAST(n.generation AS TEXT)=CAST(json_extract(s.canonical_json,'$.scope.generation') "
            "AS TEXT) AND n.status='connected' AND n.error_code IS NULL AND "
            'n.workspace_integration_id=a.connection_id AND '
            'n.external_account_id=a.external_account_id)) OR (CAST(a.platform AS '
            "TEXT)='google_ads' AND EXISTS(SELECT 1 FROM google_customer_connections n WHERE "
            'n.workspace_id=a.workspace_id AND n.account_id=a.id AND CAST(n.id AS '
            "TEXT)=json_extract(s.canonical_json,'$.scope.source_connection_ref') AND "
            "CAST(n.generation AS TEXT)=CAST(json_extract(s.canonical_json,'$.scope.generation') "
            "AS TEXT) AND n.status='connected' AND n.error_code IS NULL AND "
            'n.integration_id=a.connection_id AND n.external_account_id=a.external_account_id)) OR '
            "(CAST(a.platform AS TEXT)='tiktok_ads' AND EXISTS(SELECT 1 FROM "
            'customer_source_connections n WHERE n.workspace_id=a.workspace_id AND '
            'n.account_id=a.id AND CAST(n.id AS '
            "TEXT)=json_extract(s.canonical_json,'$.scope.source_connection_ref') AND "
            "CAST(n.generation AS TEXT)=CAST(json_extract(s.canonical_json,'$.scope.generation') "
            "AS TEXT) AND n.status='connected' AND n.error_code IS NULL AND "
            'n.integration_id=a.connection_id AND n.external_id=a.external_account_id AND '
            "n.provider='tiktok_ads'))))))),0) BEGIN SELECT RAISE(ABORT,'immutable selected "
            "reporting'); END",
            'CREATE TRIGGER customer_event_selection_current_erase AFTER DELETE ON '
            'customer_event_selection_current BEGIN DELETE FROM selected_reporting_captures WHERE '
            'workspace_id=OLD.workspace_id AND account_id=OLD.account_id;DELETE FROM '
            'initial_calibration_runs WHERE workspace_id=OLD.workspace_id AND '
            'account_id=OLD.account_id;UPDATE workspaces SET '
            'export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id; END',
            '\n'
            'CREATE TABLE selected_reporting_captures (\n'
            '\tid VARCHAR(32) NOT NULL, \n'
            '\tselection_id VARCHAR(32) NOT NULL, \n'
            '\tselection_digest VARCHAR(64) NOT NULL, \n'
            '\tcompletion_id VARCHAR(32) NOT NULL, \n'
            '\trequest_digest VARCHAR(64) NOT NULL, \n'
            '\tfact_count INTEGER NOT NULL, \n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\taccount_id INTEGER NOT NULL, \n'
            '\tconnection_id INTEGER NOT NULL, \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tpayload_digest VARCHAR(64) NOT NULL, \n'
            '\tpayload_bytes INTEGER NOT NULL, \n'
            '\tPRIMARY KEY (id), \n'
            '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
            'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
            '\tCONSTRAINT uq_selected_capture_scope UNIQUE (id, account_id, workspace_id), \n'
            '\tFOREIGN KEY(selection_id, account_id, workspace_id, selection_digest) REFERENCES '
            'customer_event_selections (id, account_id, workspace_id, payload_digest) ON DELETE '
            'CASCADE, \n'
            '\tFOREIGN KEY(completion_id, account_id, workspace_id) REFERENCES '
            'campaign_performance_completions (id, account_id, workspace_id) ON DELETE CASCADE, \n'
            '\tCONSTRAINT ck_selected_count CHECK (fact_count >= 0 AND fact_count <= 50000), \n'
            '\tCONSTRAINT ck_selected_header_bytes CHECK (payload_bytes > 0 AND payload_bytes <= '
            '16384)\n'
            ')\n'
            '\n',
            'CREATE TRIGGER selected_reporting_captures_binding BEFORE INSERT ON '
            'selected_reporting_captures WHEN NOT '
            'COALESCE((NEW.payload_bytes=length(CAST(NEW.canonical_json AS BLOB)) AND EXISTS '
            '(SELECT 1 FROM customer_event_selections s WHERE s.id=NEW.selection_id AND '
            's.connection_id=NEW.connection_id AND s.workspace_id=NEW.workspace_id AND '
            's.account_id=NEW.account_id) AND json_extract(NEW.canonical_json, '
            "'$.schema_version')='inlet.selected-capture.v1' AND "
            "CAST(json_extract(NEW.canonical_json, '$.request.capture_id') AS TEXT)=CAST(NEW.id AS "
            'TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.request.aggregate.scope.workspace_id') AS TEXT)=CAST(NEW.workspace_id AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.request.aggregate.scope.account_id') AS "
            'TEXT)=CAST(NEW.account_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.request.aggregate.scope.connection_id') AS TEXT)=CAST(NEW.connection_id AS TEXT) "
            "AND CAST(json_extract(NEW.canonical_json, '$.request.selection.selection_id') AS "
            'TEXT)=CAST(NEW.selection_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.request.selection_digest') AS TEXT)=CAST(NEW.selection_digest AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.request.aggregate.completion_id') AS "
            'TEXT)=CAST(NEW.completion_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.request_digest') AS TEXT)=CAST(NEW.request_digest AS TEXT) AND (SELECT "
            "foreign_keys FROM pragma_foreign_keys)=1),0) BEGIN SELECT RAISE(ABORT,'selected "
            "binding mismatch'); END",
            'CREATE TRIGGER selected_reporting_captures_immutable BEFORE UPDATE ON '
            "selected_reporting_captures BEGIN SELECT RAISE(ABORT,'immutable selected reporting'); "
            'END',
            'CREATE TRIGGER selected_reporting_captures_erase AFTER DELETE ON '
            'selected_reporting_captures BEGIN DELETE FROM initial_calibration_runs WHERE '
            'workspace_id=OLD.workspace_id AND account_id=OLD.account_id;UPDATE workspaces SET '
            'export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id; END',
            '\n'
            'CREATE TABLE selected_reporting_facts (\n'
            '\tcapture_id VARCHAR(32) NOT NULL, \n'
            '\tcampaign_id INTEGER NOT NULL, \n'
            '\tmetric_date DATE NOT NULL, \n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\taccount_id INTEGER NOT NULL, \n'
            '\tnative_campaign_id VARCHAR(32) NOT NULL, \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tpayload_digest VARCHAR(64) NOT NULL, \n'
            '\tpayload_bytes INTEGER NOT NULL, \n'
            '\tPRIMARY KEY (capture_id, campaign_id, metric_date), \n'
            '\tFOREIGN KEY(capture_id, account_id, workspace_id) REFERENCES '
            'selected_reporting_captures (id, account_id, workspace_id) ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(campaign_id, account_id) REFERENCES campaigns (id, account_id) ON '
            'DELETE CASCADE, \n'
            '\tCONSTRAINT uq_selected_native_day UNIQUE (capture_id, native_campaign_id, '
            'metric_date), \n'
            '\tCONSTRAINT ck_selected_fact_bytes CHECK (payload_bytes > 0 AND payload_bytes <= '
            '4096)\n'
            ')\n'
            '\n',
            'CREATE TRIGGER selected_reporting_facts_binding BEFORE INSERT ON '
            'selected_reporting_facts WHEN NOT '
            'COALESCE((NEW.payload_bytes=length(CAST(NEW.canonical_json AS BLOB)) AND EXISTS '
            '(SELECT 1 FROM campaigns c JOIN selected_reporting_captures h ON h.id=NEW.capture_id '
            'WHERE c.id=NEW.campaign_id AND c.account_id=NEW.account_id AND '
            'c.external_campaign_id=NEW.native_campaign_id AND h.workspace_id=NEW.workspace_id AND '
            'h.account_id=NEW.account_id) AND EXISTS(SELECT 1 FROM selected_reporting_captures h '
            'JOIN campaigns c ON c.id=NEW.campaign_id AND c.account_id=NEW.account_id WHERE '
            'h.id=NEW.capture_id AND CAST(c.platform AS '
            "TEXT)=json_extract(h.canonical_json,'$.request.aggregate.scope.platform')) AND "
            "json_extract(NEW.canonical_json, '$.schema_version')='inlet.selected-campaign-day.v1' "
            "AND CAST(json_extract(NEW.canonical_json, '$.capture_id') AS "
            'TEXT)=CAST(NEW.capture_id AS TEXT) AND CAST(json_extract(NEW.canonical_json, '
            "'$.campaign_id') AS TEXT)=CAST(NEW.campaign_id AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json, '$.metric_date') AS TEXT)=CAST(NEW.metric_date "
            "AS TEXT) AND CAST(json_extract(NEW.canonical_json, '$.native_campaign_id') AS "
            'TEXT)=CAST(NEW.native_campaign_id AS TEXT) AND (SELECT foreign_keys FROM '
            "pragma_foreign_keys)=1),0) BEGIN SELECT RAISE(ABORT,'selected binding mismatch'); END",
            'CREATE TRIGGER selected_reporting_facts_immutable BEFORE UPDATE ON '
            "selected_reporting_facts BEGIN SELECT RAISE(ABORT,'immutable selected reporting'); "
            'END',
            'CREATE TRIGGER selected_reporting_facts_erase AFTER DELETE ON '
            'selected_reporting_facts BEGIN DELETE FROM selected_reporting_captures WHERE '
            'id=OLD.capture_id AND workspace_id=OLD.workspace_id;DELETE FROM '
            'initial_calibration_runs WHERE workspace_id=OLD.workspace_id AND '
            'account_id=OLD.account_id;UPDATE workspaces SET '
            'export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id; END')}
