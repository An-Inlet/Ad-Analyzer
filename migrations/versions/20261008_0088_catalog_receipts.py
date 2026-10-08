# ruff: noqa: E501
"""Owned exact catalog receipts and immutable planning input observation links."""
import sqlalchemy as sa
from alembic import op

revision = "20261008_0088"
down_revision = "20261008_0087"
branch_labels = None
depends_on = None

TABLES = ('planning_catalog_receipts', 'planning_catalog_receipt_selections', 'planning_input_catalog_receipts')


def upgrade() -> None:
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    connection = op.get_bind()
    if any(connection.scalar(sa.text(f"SELECT EXISTS(SELECT 1 FROM {name})")) for name in TABLES):
        raise RuntimeError("cannot discard retained catalog receipts")
    for name in reversed(TABLES):
        op.drop_table(name)
        if connection.dialect.name == "postgresql":
            for kind in ("immutable", "binding"):
                op.execute(f"DROP FUNCTION IF EXISTS {name}_{kind}_fn()")


# Frozen DDL: never import application models in a historical migration.
SQL = {'postgresql': ('\n'
                'CREATE TABLE planning_catalog_receipts (\n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\tid VARCHAR(32) NOT NULL, \n'
                '\taccount_id INTEGER NOT NULL, \n'
                '\tconnection_id INTEGER NOT NULL, \n'
                '\tactor_id VARCHAR(32) NOT NULL, \n'
                '\tsession_digest VARCHAR(64) NOT NULL, \n'
                '\tauthenticated_at BIGINT NOT NULL, \n'
                '\tprivacy_revision INTEGER NOT NULL, \n'
                '\tsource_revision VARCHAR(2000) NOT NULL, \n'
                '\tsource_binding_digest VARCHAR(64) NOT NULL, \n'
                '\tpayload_schema VARCHAR(64) NOT NULL, \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tpayload_digest VARCHAR(64) NOT NULL, \n'
                '\tpayload_bytes INTEGER NOT NULL, \n'
                '\tcomposite_digest VARCHAR(64) NOT NULL, \n'
                '\ttarget_count INTEGER NOT NULL, \n'
                '\treporting_starts_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\treporting_ends_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tobservation_started_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tobserved_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (workspace_id, id), \n'
                '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES advertising_accounts (id, '
                'workspace_id, connection_id) ON DELETE RESTRICT, \n'
                '\tCONSTRAINT uq_catalog_receipt_owned_source UNIQUE (workspace_id, id, account_id, '
                'connection_id), \n'
                '\tCONSTRAINT uq_catalog_receipt_exact_read UNIQUE (workspace_id, actor_id, session_digest, '
                'account_id, composite_digest), \n'
                '\tCONSTRAINT ck_catalog_receipt_privacy CHECK (privacy_revision >= 0), \n'
                '\tCONSTRAINT ck_catalog_receipt_bytes CHECK (payload_bytes >= 1 AND payload_bytes <= '
                '1048576), \n'
                '\tCONSTRAINT ck_catalog_receipt_targets CHECK (target_count >= 0 AND target_count <= '
                '400), \n'
                '\tCONSTRAINT ck_catalog_receipt_schema CHECK (payload_schema = '
                "'inlet.planning-catalog-receipt.v1'), \n"
                '\tCONSTRAINT ck_catalog_receipt_times CHECK (reporting_starts_at < reporting_ends_at AND '
                'reporting_ends_at <= observation_started_at AND observation_started_at <= observed_at AND '
                'observed_at < expires_at AND created_at >= observed_at AND created_at < expires_at), \n'
                '\tFOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE\n'
                ')\n'
                '\n',
                'CREATE INDEX ix_catalog_receipts_expiry ON planning_catalog_receipts (workspace_id, '
                'expires_at, id)',
                'CREATE FUNCTION planning_catalog_receipts_binding_fn() RETURNS trigger LANGUAGE plpgsql AS '
                '$$ BEGIN IF NOT (EXISTS (SELECT 1 FROM customer_sessions s JOIN customer_memberships m ON '
                'm.user_id=s.user_id WHERE s.digest=NEW.session_digest AND s.user_id=NEW.actor_id AND '
                's.authenticated_at=NEW.authenticated_at AND m.workspace_id=NEW.workspace_id AND '
                "m.role='owner' AND m.status='active') AND "
                "NEW.payload_bytes=octet_length(NEW.canonical_json)) THEN RAISE EXCEPTION 'catalog receipt "
                "binding mismatch'; END IF; RETURN NEW; END; $$",
                'CREATE TRIGGER planning_catalog_receipts_binding BEFORE INSERT ON planning_catalog_receipts '
                'FOR EACH ROW EXECUTE FUNCTION planning_catalog_receipts_binding_fn()',
                'CREATE FUNCTION planning_catalog_receipts_immutable_fn() RETURNS trigger LANGUAGE plpgsql '
                "AS $$ BEGIN RAISE EXCEPTION 'immutable catalog receipt'; END; $$",
                'CREATE TRIGGER planning_catalog_receipts_immutable BEFORE UPDATE ON '
                'planning_catalog_receipts FOR EACH ROW EXECUTE FUNCTION '
                'planning_catalog_receipts_immutable_fn()',
                '\n'
                'CREATE TABLE planning_catalog_receipt_selections (\n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\taccount_id INTEGER NOT NULL, \n'
                '\tselection_key VARCHAR(64) NOT NULL, \n'
                '\treceipt_id VARCHAR(32) NOT NULL, \n'
                '\tconnection_id INTEGER NOT NULL, \n'
                '\tcanonical_entity_key VARCHAR(64) NOT NULL, \n'
                '\tPRIMARY KEY (workspace_id, account_id, selection_key), \n'
                '\tFOREIGN KEY(workspace_id, receipt_id, account_id, connection_id) REFERENCES '
                'planning_catalog_receipts (workspace_id, id, account_id, connection_id) ON DELETE '
                'CASCADE, \n'
                '\tCONSTRAINT uq_catalog_receipt_canonical UNIQUE (workspace_id, receipt_id, '
                'canonical_entity_key)\n'
                ')\n'
                '\n',
                'CREATE FUNCTION planning_catalog_receipt_selections_immutable_fn() RETURNS trigger LANGUAGE '
                "plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable catalog receipt'; END; $$",
                'CREATE TRIGGER planning_catalog_receipt_selections_immutable BEFORE UPDATE ON '
                'planning_catalog_receipt_selections FOR EACH ROW EXECUTE FUNCTION '
                'planning_catalog_receipt_selections_immutable_fn()',
                '\n'
                'CREATE TABLE planning_input_catalog_receipts (\n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\tplan_id VARCHAR(32) NOT NULL, \n'
                '\tinput_revision INTEGER NOT NULL, \n'
                '\taccount_id INTEGER NOT NULL, \n'
                '\treceipt_id VARCHAR(32) NOT NULL, \n'
                '\tconnection_id INTEGER NOT NULL, \n'
                '\tcomposite_digest VARCHAR(64) NOT NULL, \n'
                '\tinput_digest VARCHAR(64) NOT NULL, \n'
                '\tselected_keys_digest VARCHAR(64) NOT NULL, \n'
                '\tselected_count INTEGER NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (workspace_id, plan_id, input_revision, account_id), \n'
                '\tFOREIGN KEY(workspace_id, plan_id, input_revision) REFERENCES planning_input_revisions '
                '(workspace_id, plan_id, revision) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(workspace_id, receipt_id, account_id, connection_id) REFERENCES '
                'planning_catalog_receipts (workspace_id, id, account_id, connection_id) ON DELETE '
                'RESTRICT, \n'
                '\tCONSTRAINT ck_input_catalog_receipt_count CHECK (selected_count >= 1 AND selected_count '
                '<= 400)\n'
                ')\n'
                '\n',
                'CREATE FUNCTION planning_input_catalog_receipts_binding_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN IF NOT (EXISTS (SELECT 1 FROM planning_input_revisions i JOIN '
                'planning_catalog_receipts r ON r.workspace_id=i.workspace_id WHERE '
                'i.workspace_id=NEW.workspace_id AND i.plan_id=NEW.plan_id AND i.revision=NEW.input_revision '
                'AND r.id=NEW.receipt_id AND r.account_id=NEW.account_id AND '
                'r.connection_id=NEW.connection_id AND i.digest=NEW.input_digest AND i.actor_id=r.actor_id '
                'AND r.composite_digest=NEW.composite_digest AND NEW.created_at>=i.created_at AND '
                "NEW.created_at<r.expires_at)) THEN RAISE EXCEPTION 'catalog receipt binding mismatch'; END "
                'IF; RETURN NEW; END; $$',
                'CREATE TRIGGER planning_input_catalog_receipts_binding BEFORE INSERT ON '
                'planning_input_catalog_receipts FOR EACH ROW EXECUTE FUNCTION '
                'planning_input_catalog_receipts_binding_fn()',
                'CREATE FUNCTION planning_input_catalog_receipts_immutable_fn() RETURNS trigger LANGUAGE '
                "plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable catalog receipt'; END; $$",
                'CREATE TRIGGER planning_input_catalog_receipts_immutable BEFORE UPDATE ON '
                'planning_input_catalog_receipts FOR EACH ROW EXECUTE FUNCTION '
                'planning_input_catalog_receipts_immutable_fn()'),
 'sqlite': ('\n'
            'CREATE TABLE planning_catalog_receipts (\n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\tid VARCHAR(32) NOT NULL, \n'
            '\taccount_id INTEGER NOT NULL, \n'
            '\tconnection_id INTEGER NOT NULL, \n'
            '\tactor_id VARCHAR(32) NOT NULL, \n'
            '\tsession_digest VARCHAR(64) NOT NULL, \n'
            '\tauthenticated_at BIGINT NOT NULL, \n'
            '\tprivacy_revision INTEGER NOT NULL, \n'
            '\tsource_revision VARCHAR(2000) NOT NULL, \n'
            '\tsource_binding_digest VARCHAR(64) NOT NULL, \n'
            '\tpayload_schema VARCHAR(64) NOT NULL, \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tpayload_digest VARCHAR(64) NOT NULL, \n'
            '\tpayload_bytes INTEGER NOT NULL, \n'
            '\tcomposite_digest VARCHAR(64) NOT NULL, \n'
            '\ttarget_count INTEGER NOT NULL, \n'
            '\treporting_starts_at DATETIME NOT NULL, \n'
            '\treporting_ends_at DATETIME NOT NULL, \n'
            '\tobservation_started_at DATETIME NOT NULL, \n'
            '\tobserved_at DATETIME NOT NULL, \n'
            '\texpires_at DATETIME NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (workspace_id, id), \n'
            '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES advertising_accounts (id, '
            'workspace_id, connection_id) ON DELETE RESTRICT, \n'
            '\tCONSTRAINT uq_catalog_receipt_owned_source UNIQUE (workspace_id, id, account_id, '
            'connection_id), \n'
            '\tCONSTRAINT uq_catalog_receipt_exact_read UNIQUE (workspace_id, actor_id, session_digest, '
            'account_id, composite_digest), \n'
            '\tCONSTRAINT ck_catalog_receipt_privacy CHECK (privacy_revision >= 0), \n'
            '\tCONSTRAINT ck_catalog_receipt_bytes CHECK (payload_bytes >= 1 AND payload_bytes <= '
            '1048576), \n'
            '\tCONSTRAINT ck_catalog_receipt_targets CHECK (target_count >= 0 AND target_count <= 400), \n'
            '\tCONSTRAINT ck_catalog_receipt_schema CHECK (payload_schema = '
            "'inlet.planning-catalog-receipt.v1'), \n"
            '\tCONSTRAINT ck_catalog_receipt_times CHECK (reporting_starts_at < reporting_ends_at AND '
            'reporting_ends_at <= observation_started_at AND observation_started_at <= observed_at AND '
            'observed_at < expires_at AND created_at >= observed_at AND created_at < expires_at), \n'
            '\tFOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE\n'
            ')\n'
            '\n',
            'CREATE INDEX ix_catalog_receipts_expiry ON planning_catalog_receipts (workspace_id, expires_at, '
            'id)',
            'CREATE TRIGGER planning_catalog_receipts_binding BEFORE INSERT ON planning_catalog_receipts '
            'WHEN NOT (EXISTS (SELECT 1 FROM customer_sessions s JOIN customer_memberships m ON '
            'm.user_id=s.user_id WHERE s.digest=NEW.session_digest AND s.user_id=NEW.actor_id AND '
            "s.authenticated_at=NEW.authenticated_at AND m.workspace_id=NEW.workspace_id AND m.role='owner' "
            "AND m.status='active') AND NEW.payload_bytes=length(CAST(NEW.canonical_json AS BLOB))) BEGIN "
            "SELECT RAISE(ABORT,'catalog receipt binding mismatch'); END",
            'CREATE TRIGGER planning_catalog_receipts_immutable BEFORE UPDATE ON planning_catalog_receipts '
            "BEGIN SELECT RAISE(ABORT,'immutable catalog receipt'); END",
            '\n'
            'CREATE TABLE planning_catalog_receipt_selections (\n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\taccount_id INTEGER NOT NULL, \n'
            '\tselection_key VARCHAR(64) NOT NULL, \n'
            '\treceipt_id VARCHAR(32) NOT NULL, \n'
            '\tconnection_id INTEGER NOT NULL, \n'
            '\tcanonical_entity_key VARCHAR(64) NOT NULL, \n'
            '\tPRIMARY KEY (workspace_id, account_id, selection_key), \n'
            '\tFOREIGN KEY(workspace_id, receipt_id, account_id, connection_id) REFERENCES '
            'planning_catalog_receipts (workspace_id, id, account_id, connection_id) ON DELETE CASCADE, \n'
            '\tCONSTRAINT uq_catalog_receipt_canonical UNIQUE (workspace_id, receipt_id, '
            'canonical_entity_key)\n'
            ')\n'
            '\n',
            'CREATE TRIGGER planning_catalog_receipt_selections_immutable BEFORE UPDATE ON '
            "planning_catalog_receipt_selections BEGIN SELECT RAISE(ABORT,'immutable catalog receipt'); END",
            '\n'
            'CREATE TABLE planning_input_catalog_receipts (\n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\tplan_id VARCHAR(32) NOT NULL, \n'
            '\tinput_revision INTEGER NOT NULL, \n'
            '\taccount_id INTEGER NOT NULL, \n'
            '\treceipt_id VARCHAR(32) NOT NULL, \n'
            '\tconnection_id INTEGER NOT NULL, \n'
            '\tcomposite_digest VARCHAR(64) NOT NULL, \n'
            '\tinput_digest VARCHAR(64) NOT NULL, \n'
            '\tselected_keys_digest VARCHAR(64) NOT NULL, \n'
            '\tselected_count INTEGER NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (workspace_id, plan_id, input_revision, account_id), \n'
            '\tFOREIGN KEY(workspace_id, plan_id, input_revision) REFERENCES planning_input_revisions '
            '(workspace_id, plan_id, revision) ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(workspace_id, receipt_id, account_id, connection_id) REFERENCES '
            'planning_catalog_receipts (workspace_id, id, account_id, connection_id) ON DELETE RESTRICT, \n'
            '\tCONSTRAINT ck_input_catalog_receipt_count CHECK (selected_count >= 1 AND selected_count <= '
            '400)\n'
            ')\n'
            '\n',
            'CREATE TRIGGER planning_input_catalog_receipts_binding BEFORE INSERT ON '
            'planning_input_catalog_receipts WHEN NOT (EXISTS (SELECT 1 FROM planning_input_revisions i JOIN '
            'planning_catalog_receipts r ON r.workspace_id=i.workspace_id WHERE '
            'i.workspace_id=NEW.workspace_id AND i.plan_id=NEW.plan_id AND i.revision=NEW.input_revision AND '
            'r.id=NEW.receipt_id AND r.account_id=NEW.account_id AND r.connection_id=NEW.connection_id AND '
            'i.digest=NEW.input_digest AND i.actor_id=r.actor_id AND r.composite_digest=NEW.composite_digest '
            'AND NEW.created_at>=i.created_at AND NEW.created_at<r.expires_at)) BEGIN SELECT '
            "RAISE(ABORT,'catalog receipt binding mismatch'); END",
            'CREATE TRIGGER planning_input_catalog_receipts_immutable BEFORE UPDATE ON '
            "planning_input_catalog_receipts BEGIN SELECT RAISE(ABORT,'immutable catalog receipt'); END")}
