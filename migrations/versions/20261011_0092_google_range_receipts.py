# ruff: noqa: E501
"""Erasable immutable owned Google range receipt; frozen SQL, no application imports."""
import sqlalchemy as sa
from alembic import op

revision = "20261011_0092"
down_revision = "20261011_0091"
branch_labels = None
depends_on = None
TABLE = "google_reporting_range_receipts"


def upgrade() -> None:
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    db = op.get_bind()
    if db.execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first() is not None:
        raise RuntimeError("range receipts must be erased before downgrade")
    op.drop_table(TABLE)
    if db.dialect.name == "postgresql":
        for kind in ("binding", "immutable", "guard", "erase"):
            op.execute(f"DROP FUNCTION IF EXISTS grr_{kind}_fn()")


SQL = {'sqlite': ('\n'
            'CREATE TABLE google_reporting_range_receipts (\n'
            '\trequest_id VARCHAR(32) NOT NULL, \n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\taccount_id INTEGER NOT NULL, \n'
            '\tconnection_id INTEGER NOT NULL, \n'
            '\tcompletion_id VARCHAR(32) NOT NULL, \n'
            '\tjob_id INTEGER NOT NULL, \n'
            '\tinitiating_customer_id VARCHAR(32) NOT NULL, \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tpayload_digest VARCHAR(64) NOT NULL, \n'
            '\tpayload_bytes INTEGER NOT NULL, \n'
            '\tPRIMARY KEY (request_id), \n'
            '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
            'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(completion_id, account_id, workspace_id) REFERENCES '
            'campaign_performance_completions (id, account_id, workspace_id) ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(job_id, workspace_id) REFERENCES job_runs (id, workspace_id) ON DELETE '
            'CASCADE, \n'
            '\tFOREIGN KEY(initiating_customer_id) REFERENCES customer_users (id) ON DELETE '
            'CASCADE, \n'
            '\tCONSTRAINT ck_range_receipt_bytes CHECK (payload_bytes > 0 AND payload_bytes <= '
            '16384)\n'
            ')\n'
            '\n',
            'CREATE TRIGGER grr_binding BEFORE INSERT ON google_reporting_range_receipts WHEN NOT '
            "COALESCE((json_extract(NEW.canonical_json,'$.schema_version')='inlet.google-reporting-range-receipt.v1' "
            "AND json_extract(NEW.canonical_json,'$.final_scope.platform')='google_ads' AND "
            "json_extract(NEW.canonical_json,'$.original_scope.platform')='google_ads' AND "
            "json_extract(NEW.canonical_json,'$.query_version')='google.v24.campaign-day.metrics-conversions.v1' "
            "AND CAST(NEW.request_id AS TEXT)=CAST(json_extract(NEW.canonical_json,'$.request_id') "
            'AS TEXT) AND CAST(NEW.workspace_id AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.workspace_id') AS TEXT) AND "
            'CAST(NEW.account_id AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.account_id') AS TEXT) AND "
            'CAST(NEW.connection_id AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.connection_id') AS TEXT) "
            'AND CAST(NEW.completion_id AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.completion_id') AS TEXT) AND "
            "CAST(NEW.job_id AS TEXT)=CAST(json_extract(NEW.canonical_json,'$.job_id') AS TEXT) "
            'AND CAST(NEW.initiating_customer_id AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.initiating_customer_id') AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json,'$.original_scope.workspace_id') AS "
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.workspace_id') AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json,'$.original_scope.account_id') AS "
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.account_id') AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json,'$.original_scope.connection_id') AS "
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.connection_id') AS TEXT) "
            "AND CAST(json_extract(NEW.canonical_json,'$.original_scope.platform') AS "
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.platform') AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json,'$.original_scope.source_connection_ref') AS "
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.source_connection_ref') AS "
            "TEXT) AND CAST(json_extract(NEW.canonical_json,'$.original_scope.generation') AS "
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.generation') AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json,'$.original_scope.native_account_id') AS "
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.native_account_id') AS "
            "TEXT) AND CAST(json_extract(NEW.canonical_json,'$.original_scope.currency') AS "
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.currency') AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json,'$.original_scope.time_zone') AS "
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.time_zone') AS TEXT) AND "
            "CAST(json_extract(NEW.canonical_json,'$.original_scope.privacy_revision') AS "
            "BIGINT)<=CAST(json_extract(NEW.canonical_json,'$.final_scope.privacy_revision') AS "
            'BIGINT) AND EXISTS(SELECT 1 FROM job_runs j WHERE j.id=NEW.job_id AND '
            'j.workspace_id=NEW.workspace_id AND j.account_id=NEW.account_id AND '
            "j.connection_id=NEW.connection_id AND CAST(j.platform AS TEXT)='google_ads' AND "
            "CAST(j.status AS TEXT)='succeeded' AND j.job_name='google_customer_range_read') AND "
            'EXISTS(SELECT 1 FROM campaign_performance_completions c WHERE c.id=NEW.completion_id '
            'AND c.account_id=NEW.account_id AND c.workspace_id=NEW.workspace_id AND '
            "c.platform='google_ads' AND CAST(c.source_connection_ref AS "
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.source_connection_ref') AS "
            'TEXT) AND CAST(c.generation AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.generation') AS TEXT) AND "
            'CAST(c.privacy_revision AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.privacy_revision') AS TEXT) "
            'AND CAST(c.currency AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.currency') AS TEXT) AND "
            'CAST(c.time_zone AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.final_scope.time_zone') AS TEXT) AND "
            'CAST(c.manifest_digest AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.manifest_digest') AS TEXT) AND "
            "CAST(c.query_version AS TEXT)=CAST(json_extract(NEW.canonical_json,'$.query_version') "
            'AS TEXT) AND CAST(c.row_count AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.row_count') AS TEXT) AND "
            'CAST(c.starts_on AS '
            "TEXT)=CAST(json_extract(NEW.canonical_json,'$.requested_starts_on') AS TEXT) AND "
            "CAST(c.ends_on AS TEXT)=CAST(json_extract(NEW.canonical_json,'$.requested_ends_on') "
            'AS TEXT) AND '
            "julianday(c.completed_at)=julianday(json_extract(NEW.canonical_json,'$.completed_at'))) "
            'AND NEW.payload_bytes=length(CAST(NEW.canonical_json AS BLOB)) AND (SELECT '
            "foreign_keys FROM pragma_foreign_keys)=1),0) BEGIN SELECT RAISE(ABORT,'range receipt "
            "binding unavailable'); END",
            'CREATE TRIGGER grr_immutable BEFORE UPDATE ON google_reporting_range_receipts BEGIN '
            "SELECT RAISE(ABORT,'immutable range receipt'); END",
            'CREATE TRIGGER grr_erase AFTER DELETE ON google_reporting_range_receipts BEGIN DELETE '
            'FROM initial_calibration_runs WHERE workspace_id=OLD.workspace_id AND '
            'account_id=OLD.account_id; UPDATE workspaces SET '
            'export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id; END'),
 'postgresql': ('\n'
                'CREATE TABLE google_reporting_range_receipts (\n'
                '\trequest_id VARCHAR(32) NOT NULL, \n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\taccount_id INTEGER NOT NULL, \n'
                '\tconnection_id INTEGER NOT NULL, \n'
                '\tcompletion_id VARCHAR(32) NOT NULL, \n'
                '\tjob_id INTEGER NOT NULL, \n'
                '\tinitiating_customer_id VARCHAR(32) NOT NULL, \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tpayload_digest VARCHAR(64) NOT NULL, \n'
                '\tpayload_bytes INTEGER NOT NULL, \n'
                '\tPRIMARY KEY (request_id), \n'
                '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
                'advertising_accounts (id, workspace_id, connection_id) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(completion_id, account_id, workspace_id) REFERENCES '
                'campaign_performance_completions (id, account_id, workspace_id) ON DELETE '
                'CASCADE, \n'
                '\tFOREIGN KEY(job_id, workspace_id) REFERENCES job_runs (id, workspace_id) ON '
                'DELETE CASCADE, \n'
                '\tFOREIGN KEY(initiating_customer_id) REFERENCES customer_users (id) ON DELETE '
                'CASCADE, \n'
                '\tCONSTRAINT ck_range_receipt_bytes CHECK (payload_bytes > 0 AND payload_bytes <= '
                '16384)\n'
                ')\n'
                '\n',
                'CREATE FUNCTION grr_binding_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF '
                'NOT COALESCE(((NEW.canonical_json::jsonb #>> '
                "'{schema_version}')='inlet.google-reporting-range-receipt.v1' AND "
                "(NEW.canonical_json::jsonb #>> '{final_scope,platform}')='google_ads' AND "
                "(NEW.canonical_json::jsonb #>> '{original_scope,platform}')='google_ads' AND "
                '(NEW.canonical_json::jsonb #>> '
                "'{query_version}')='google.v24.campaign-day.metrics-conversions.v1' AND "
                "CAST(NEW.request_id AS TEXT)=CAST((NEW.canonical_json::jsonb #>> '{request_id}') "
                'AS TEXT) AND CAST(NEW.workspace_id AS TEXT)=CAST((NEW.canonical_json::jsonb #>> '
                "'{final_scope,workspace_id}') AS TEXT) AND CAST(NEW.account_id AS "
                "TEXT)=CAST((NEW.canonical_json::jsonb #>> '{final_scope,account_id}') AS TEXT) "
                'AND CAST(NEW.connection_id AS TEXT)=CAST((NEW.canonical_json::jsonb #>> '
                "'{final_scope,connection_id}') AS TEXT) AND CAST(NEW.completion_id AS "
                "TEXT)=CAST((NEW.canonical_json::jsonb #>> '{completion_id}') AS TEXT) AND "
                "CAST(NEW.job_id AS TEXT)=CAST((NEW.canonical_json::jsonb #>> '{job_id}') AS TEXT) "
                'AND CAST(NEW.initiating_customer_id AS TEXT)=CAST((NEW.canonical_json::jsonb #>> '
                "'{initiating_customer_id}') AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
                "'{original_scope,workspace_id}') AS TEXT)=CAST((NEW.canonical_json::jsonb #>> "
                "'{final_scope,workspace_id}') AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
                "'{original_scope,account_id}') AS TEXT)=CAST((NEW.canonical_json::jsonb #>> "
                "'{final_scope,account_id}') AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
                "'{original_scope,connection_id}') AS TEXT)=CAST((NEW.canonical_json::jsonb #>> "
                "'{final_scope,connection_id}') AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
                "'{original_scope,platform}') AS TEXT)=CAST((NEW.canonical_json::jsonb #>> "
                "'{final_scope,platform}') AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> "
                "'{original_scope,source_connection_ref}') AS "
                "TEXT)=CAST((NEW.canonical_json::jsonb #>> '{final_scope,source_connection_ref}') "
                "AS TEXT) AND CAST((NEW.canonical_json::jsonb #>> '{original_scope,generation}') "
                "AS TEXT)=CAST((NEW.canonical_json::jsonb #>> '{final_scope,generation}') AS TEXT) "
                "AND CAST((NEW.canonical_json::jsonb #>> '{original_scope,native_account_id}') AS "
                "TEXT)=CAST((NEW.canonical_json::jsonb #>> '{final_scope,native_account_id}') AS "
                "TEXT) AND CAST((NEW.canonical_json::jsonb #>> '{original_scope,currency}') AS "
                "TEXT)=CAST((NEW.canonical_json::jsonb #>> '{final_scope,currency}') AS TEXT) AND "
                "CAST((NEW.canonical_json::jsonb #>> '{original_scope,time_zone}') AS "
                "TEXT)=CAST((NEW.canonical_json::jsonb #>> '{final_scope,time_zone}') AS TEXT) AND "
                "CAST((NEW.canonical_json::jsonb #>> '{original_scope,privacy_revision}') AS "
                "BIGINT)<=CAST((NEW.canonical_json::jsonb #>> '{final_scope,privacy_revision}') AS "
                'BIGINT) AND EXISTS(SELECT 1 FROM job_runs j WHERE j.id=NEW.job_id AND '
                'j.workspace_id=NEW.workspace_id AND j.account_id=NEW.account_id AND '
                "j.connection_id=NEW.connection_id AND CAST(j.platform AS TEXT)='google_ads' AND "
                "CAST(j.status AS TEXT)='succeeded' AND j.job_name='google_customer_range_read') "
                'AND EXISTS(SELECT 1 FROM campaign_performance_completions c WHERE '
                'c.id=NEW.completion_id AND c.account_id=NEW.account_id AND '
                "c.workspace_id=NEW.workspace_id AND c.platform='google_ads' AND "
                'CAST(c.source_connection_ref AS TEXT)=CAST((NEW.canonical_json::jsonb #>> '
                "'{final_scope,source_connection_ref}') AS TEXT) AND CAST(c.generation AS "
                "TEXT)=CAST((NEW.canonical_json::jsonb #>> '{final_scope,generation}') AS TEXT) "
                'AND CAST(c.privacy_revision AS TEXT)=CAST((NEW.canonical_json::jsonb #>> '
                "'{final_scope,privacy_revision}') AS TEXT) AND CAST(c.currency AS "
                "TEXT)=CAST((NEW.canonical_json::jsonb #>> '{final_scope,currency}') AS TEXT) AND "
                'CAST(c.time_zone AS TEXT)=CAST((NEW.canonical_json::jsonb #>> '
                "'{final_scope,time_zone}') AS TEXT) AND CAST(c.manifest_digest AS "
                "TEXT)=CAST((NEW.canonical_json::jsonb #>> '{manifest_digest}') AS TEXT) AND "
                'CAST(c.query_version AS TEXT)=CAST((NEW.canonical_json::jsonb #>> '
                "'{query_version}') AS TEXT) AND CAST(c.row_count AS "
                "TEXT)=CAST((NEW.canonical_json::jsonb #>> '{row_count}') AS TEXT) AND "
                'CAST(c.starts_on AS TEXT)=CAST((NEW.canonical_json::jsonb #>> '
                "'{requested_starts_on}') AS TEXT) AND CAST(c.ends_on AS "
                "TEXT)=CAST((NEW.canonical_json::jsonb #>> '{requested_ends_on}') AS TEXT) AND "
                "c.completed_at=CAST((NEW.canonical_json::jsonb #>> '{completed_at}') AS TIMESTAMP "
                'WITH TIME ZONE)) AND NEW.payload_bytes=octet_length(NEW.canonical_json)),false) '
                "THEN RAISE EXCEPTION 'range receipt binding unavailable'; END IF; RETURN NEW; "
                'END; $$',
                'CREATE TRIGGER grr_binding BEFORE INSERT ON google_reporting_range_receipts FOR '
                'EACH ROW EXECUTE FUNCTION grr_binding_fn()',
                'CREATE FUNCTION grr_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN '
                "RAISE EXCEPTION 'immutable range receipt'; END; $$",
                'CREATE TRIGGER grr_immutable BEFORE UPDATE ON google_reporting_range_receipts FOR '
                'EACH ROW EXECUTE FUNCTION grr_immutable_fn()',
                'CREATE FUNCTION grr_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN '
                'PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; RETURN '
                'OLD; END; $$',
                'CREATE TRIGGER grr_guard BEFORE DELETE ON google_reporting_range_receipts FOR '
                'EACH ROW EXECUTE FUNCTION grr_guard_fn()',
                'CREATE FUNCTION grr_erase_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN '
                'DELETE FROM initial_calibration_runs WHERE workspace_id=OLD.workspace_id AND '
                'account_id=OLD.account_id; UPDATE workspaces SET '
                'export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id; '
                'RETURN NULL; END; $$',
                'CREATE TRIGGER grr_erase AFTER DELETE ON google_reporting_range_receipts FOR EACH '
                'ROW EXECUTE FUNCTION grr_erase_fn()')}
