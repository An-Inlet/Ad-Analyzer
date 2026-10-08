# ruff: noqa: E501
"""Owned erasable planning documents, history, evidence dependencies and receipts."""
import sqlalchemy as sa
from alembic import op

revision = "20261008_0087"
down_revision = "20261008_0086"
branch_labels = None
depends_on = None

TABLES = ('planning_documents', 'planning_input_revisions', 'planning_document_versions', 'planning_document_dependencies', 'planning_document_events', 'planning_document_requests')


def upgrade() -> None:
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    connection = op.get_bind()
    if any(connection.scalar(sa.text(f"SELECT EXISTS(SELECT 1 FROM {name})")) for name in TABLES):
        raise RuntimeError("cannot discard retained planning documents")
    for name in reversed(TABLES):
        op.drop_table(name)
        if connection.dialect.name == "postgresql":
            op.execute(f"DROP FUNCTION IF EXISTS {name}_immutable_fn()")
            op.execute(f"DROP FUNCTION IF EXISTS {name}_binding_fn()")


# Frozen DDL, no application model imports during migration.
SQL = {'postgresql': ('\n'
                'CREATE TABLE planning_documents (\n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\tid VARCHAR(32) NOT NULL, \n'
                '\tinput_head INTEGER NOT NULL, \n'
                '\tversion_head INTEGER NOT NULL, \n'
                '\tevent_sequence INTEGER NOT NULL, \n'
                '\tcreated_by VARCHAR(32) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (workspace_id, id), \n'
                '\tCONSTRAINT ck_planning_heads CHECK (input_head >= 1 AND version_head >= 0 AND '
                'event_sequence >= 0), \n'
                '\tFOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE\n'
                ')\n'
                '\n',
                '\n'
                'CREATE TABLE planning_input_revisions (\n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\tplan_id VARCHAR(32) NOT NULL, \n'
                '\trevision INTEGER NOT NULL, \n'
                '\tgoal_id VARCHAR(32) NOT NULL, \n'
                '\tgoal_revision INTEGER NOT NULL, \n'
                '\tconfirmed_preview_id VARCHAR(32) NOT NULL, \n'
                '\tdefinition_digest VARCHAR(64) NOT NULL, \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tdigest VARCHAR(64) NOT NULL, \n'
                '\tactor_id VARCHAR(32) NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tPRIMARY KEY (workspace_id, plan_id, revision), \n'
                '\tFOREIGN KEY(workspace_id, plan_id) REFERENCES planning_documents (workspace_id, '
                'id) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(goal_id, workspace_id) REFERENCES customer_goals (id, workspace_id) '
                'ON DELETE RESTRICT, \n'
                '\tFOREIGN KEY(goal_id, goal_revision) REFERENCES customer_goal_revisions '
                '(goal_id, revision) ON DELETE RESTRICT, \n'
                '\tFOREIGN KEY(confirmed_preview_id) REFERENCES customer_goal_previews (id) ON '
                'DELETE RESTRICT, \n'
                '\tCONSTRAINT ck_planning_input_revision CHECK (revision >= 1 AND goal_revision >= '
                '1)\n'
                ')\n'
                '\n',
                'CREATE FUNCTION planning_input_revisions_binding_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN IF NOT (EXISTS (SELECT 1 FROM customer_goal_previews p WHERE '
                'p.id=NEW.confirmed_preview_id AND p.goal_id=NEW.goal_id AND '
                "p.revision=NEW.goal_revision)) THEN RAISE EXCEPTION 'planning binding mismatch'; "
                'END IF; RETURN NEW; END; $$',
                'CREATE TRIGGER planning_input_revisions_binding BEFORE INSERT ON '
                'planning_input_revisions FOR EACH ROW EXECUTE FUNCTION '
                'planning_input_revisions_binding_fn()',
                'CREATE FUNCTION planning_input_revisions_immutable_fn() RETURNS trigger LANGUAGE '
                "plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable planning history'; END; $$",
                'CREATE TRIGGER planning_input_revisions_immutable BEFORE UPDATE ON '
                'planning_input_revisions FOR EACH ROW EXECUTE FUNCTION '
                'planning_input_revisions_immutable_fn()',
                '\n'
                'CREATE TABLE planning_document_versions (\n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\tplan_id VARCHAR(32) NOT NULL, \n'
                '\tversion INTEGER NOT NULL, \n'
                '\tinput_revision INTEGER NOT NULL, \n'
                '\tparent_digest VARCHAR(64), \n'
                '\tdigest VARCHAR(64) NOT NULL, \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tgenerator_version VARCHAR(2000) NOT NULL, \n'
                '\tpolicy_version VARCHAR(2000) NOT NULL, \n'
                '\tactor_id VARCHAR(32) NOT NULL, \n'
                '\tgenerated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tvalid_until TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tprivacy_revision INTEGER NOT NULL, \n'
                '\tPRIMARY KEY (workspace_id, plan_id, version), \n'
                '\tFOREIGN KEY(workspace_id, plan_id) REFERENCES planning_documents (workspace_id, '
                'id) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(workspace_id, plan_id, input_revision) REFERENCES '
                'planning_input_revisions (workspace_id, plan_id, revision) ON DELETE RESTRICT, \n'
                '\tCONSTRAINT ck_planning_version CHECK (version >= 1 AND privacy_revision >= 0)\n'
                ')\n'
                '\n',
                'CREATE FUNCTION planning_document_versions_immutable_fn() RETURNS trigger '
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable planning history'; END; "
                '$$',
                'CREATE TRIGGER planning_document_versions_immutable BEFORE UPDATE ON '
                'planning_document_versions FOR EACH ROW EXECUTE FUNCTION '
                'planning_document_versions_immutable_fn()',
                '\n'
                'CREATE TABLE planning_document_dependencies (\n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\tplan_id VARCHAR(32) NOT NULL, \n'
                '\tversion INTEGER NOT NULL, \n'
                '\tevidence_key VARCHAR(96) NOT NULL, \n'
                '\taccount_id INTEGER, \n'
                '\tconnection_id INTEGER, \n'
                '\tstore_id VARCHAR(32), \n'
                '\tkind VARCHAR(32) NOT NULL, \n'
                '\tsource_binding_digest VARCHAR(64) NOT NULL, \n'
                '\tdocument_digest VARCHAR(64) NOT NULL, \n'
                '\tsource_revision VARCHAR(160) NOT NULL, \n'
                '\tobserved_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tprivacy_revision INTEGER NOT NULL, \n'
                '\tPRIMARY KEY (workspace_id, plan_id, version, evidence_key), \n'
                '\tFOREIGN KEY(workspace_id, plan_id, version) REFERENCES '
                'planning_document_versions (workspace_id, plan_id, version) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
                'advertising_accounts (id, workspace_id, connection_id) ON DELETE RESTRICT, \n'
                '\tFOREIGN KEY(store_id, workspace_id) REFERENCES commerce_stores (id, '
                'workspace_id) ON DELETE RESTRICT, \n'
                '\tCONSTRAINT ck_planning_dependency_account CHECK ((account_id IS NULL) = '
                '(connection_id IS NULL)), \n'
                '\tCONSTRAINT ck_planning_dependency_privacy CHECK (privacy_revision >= 0)\n'
                ')\n'
                '\n',
                'CREATE FUNCTION planning_document_dependencies_immutable_fn() RETURNS trigger '
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable planning history'; END; "
                '$$',
                'CREATE TRIGGER planning_document_dependencies_immutable BEFORE UPDATE ON '
                'planning_document_dependencies FOR EACH ROW EXECUTE FUNCTION '
                'planning_document_dependencies_immutable_fn()',
                '\n'
                'CREATE TABLE planning_document_events (\n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\tplan_id VARCHAR(32) NOT NULL, \n'
                '\tsequence INTEGER NOT NULL, \n'
                '\tevent_id VARCHAR(32) NOT NULL, \n'
                '\tversion INTEGER NOT NULL, \n'
                '\taction_key VARCHAR(96) NOT NULL, \n'
                '\taction_digest VARCHAR(64) NOT NULL, \n'
                '\tkind VARCHAR(16) NOT NULL, \n'
                '\tactor_id VARCHAR(32) NOT NULL, \n'
                '\trecorded_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                '\tprior_sequence INTEGER, \n'
                '\tcanonical_json TEXT NOT NULL, \n'
                '\tdigest VARCHAR(64) NOT NULL, \n'
                '\tPRIMARY KEY (workspace_id, plan_id, sequence), \n'
                '\tFOREIGN KEY(workspace_id, plan_id, version) REFERENCES '
                'planning_document_versions (workspace_id, plan_id, version) ON DELETE CASCADE, \n'
                '\tCONSTRAINT uq_planning_event_id UNIQUE (workspace_id, event_id), \n'
                '\tFOREIGN KEY(workspace_id, plan_id, prior_sequence) REFERENCES '
                'planning_document_events (workspace_id, plan_id, sequence) ON DELETE RESTRICT, \n'
                '\tCONSTRAINT ck_planning_event_order CHECK (sequence >= 1 AND (prior_sequence IS '
                'NULL OR prior_sequence < sequence)), \n'
                '\tCONSTRAINT ck_planning_event_kind CHECK (kind IN '
                "('decision','assertion','observation'))\n"
                ')\n'
                '\n',
                'CREATE FUNCTION planning_document_events_binding_fn() RETURNS trigger LANGUAGE '
                'plpgsql AS $$ BEGIN IF NOT (NEW.prior_sequence IS NULL OR EXISTS (SELECT 1 FROM '
                'planning_document_events p WHERE p.workspace_id=NEW.workspace_id AND '
                'p.plan_id=NEW.plan_id AND p.sequence=NEW.prior_sequence AND p.version=NEW.version '
                'AND p.action_key=NEW.action_key AND p.kind=NEW.kind)) THEN RAISE EXCEPTION '
                "'planning binding mismatch'; END IF; RETURN NEW; END; $$",
                'CREATE TRIGGER planning_document_events_binding BEFORE INSERT ON '
                'planning_document_events FOR EACH ROW EXECUTE FUNCTION '
                'planning_document_events_binding_fn()',
                'CREATE FUNCTION planning_document_events_immutable_fn() RETURNS trigger LANGUAGE '
                "plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable planning history'; END; $$",
                'CREATE TRIGGER planning_document_events_immutable BEFORE UPDATE ON '
                'planning_document_events FOR EACH ROW EXECUTE FUNCTION '
                'planning_document_events_immutable_fn()',
                '\n'
                'CREATE TABLE planning_document_requests (\n'
                '\tworkspace_id INTEGER NOT NULL, \n'
                '\tactor_id VARCHAR(32) NOT NULL, \n'
                '\toperation VARCHAR(32) NOT NULL, \n'
                '\trequest_key VARCHAR(128) NOT NULL, \n'
                '\trequest_digest VARCHAR(64) NOT NULL, \n'
                '\tplan_id VARCHAR(32) NOT NULL, \n'
                '\tresult_kind VARCHAR(16) NOT NULL, \n'
                '\tinput_revision INTEGER, \n'
                '\tversion INTEGER, \n'
                '\tevent_sequence INTEGER, \n'
                '\tPRIMARY KEY (workspace_id, actor_id, operation, request_key), \n'
                '\tFOREIGN KEY(workspace_id, plan_id) REFERENCES planning_documents (workspace_id, '
                'id) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(workspace_id, plan_id, input_revision) REFERENCES '
                'planning_input_revisions (workspace_id, plan_id, revision) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(workspace_id, plan_id, version) REFERENCES '
                'planning_document_versions (workspace_id, plan_id, version) ON DELETE CASCADE, \n'
                '\tFOREIGN KEY(workspace_id, plan_id, event_sequence) REFERENCES '
                'planning_document_events (workspace_id, plan_id, sequence) ON DELETE CASCADE, \n'
                "\tCONSTRAINT ck_planning_request_result CHECK ((result_kind = 'input' AND "
                'input_revision IS NOT NULL AND version IS NULL AND event_sequence IS NULL) OR '
                "(result_kind = 'version' AND version IS NOT NULL AND input_revision IS NULL AND "
                "event_sequence IS NULL) OR (result_kind = 'event' AND event_sequence IS NOT NULL "
                'AND input_revision IS NULL AND version IS NULL))\n'
                ')\n'
                '\n',
                'CREATE FUNCTION planning_document_requests_immutable_fn() RETURNS trigger '
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable planning history'; END; "
                '$$',
                'CREATE TRIGGER planning_document_requests_immutable BEFORE UPDATE ON '
                'planning_document_requests FOR EACH ROW EXECUTE FUNCTION '
                'planning_document_requests_immutable_fn()'),
 'sqlite': ('\n'
            'CREATE TABLE planning_documents (\n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\tid VARCHAR(32) NOT NULL, \n'
            '\tinput_head INTEGER NOT NULL, \n'
            '\tversion_head INTEGER NOT NULL, \n'
            '\tevent_sequence INTEGER NOT NULL, \n'
            '\tcreated_by VARCHAR(32) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (workspace_id, id), \n'
            '\tCONSTRAINT ck_planning_heads CHECK (input_head >= 1 AND version_head >= 0 AND '
            'event_sequence >= 0), \n'
            '\tFOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE\n'
            ')\n'
            '\n',
            '\n'
            'CREATE TABLE planning_input_revisions (\n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\tplan_id VARCHAR(32) NOT NULL, \n'
            '\trevision INTEGER NOT NULL, \n'
            '\tgoal_id VARCHAR(32) NOT NULL, \n'
            '\tgoal_revision INTEGER NOT NULL, \n'
            '\tconfirmed_preview_id VARCHAR(32) NOT NULL, \n'
            '\tdefinition_digest VARCHAR(64) NOT NULL, \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tdigest VARCHAR(64) NOT NULL, \n'
            '\tactor_id VARCHAR(32) NOT NULL, \n'
            '\tcreated_at DATETIME NOT NULL, \n'
            '\tPRIMARY KEY (workspace_id, plan_id, revision), \n'
            '\tFOREIGN KEY(workspace_id, plan_id) REFERENCES planning_documents (workspace_id, id) '
            'ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(goal_id, workspace_id) REFERENCES customer_goals (id, workspace_id) ON '
            'DELETE RESTRICT, \n'
            '\tFOREIGN KEY(goal_id, goal_revision) REFERENCES customer_goal_revisions (goal_id, '
            'revision) ON DELETE RESTRICT, \n'
            '\tFOREIGN KEY(confirmed_preview_id) REFERENCES customer_goal_previews (id) ON DELETE '
            'RESTRICT, \n'
            '\tCONSTRAINT ck_planning_input_revision CHECK (revision >= 1 AND goal_revision >= 1)\n'
            ')\n'
            '\n',
            'CREATE TRIGGER planning_input_revisions_binding BEFORE INSERT ON '
            'planning_input_revisions WHEN NOT (EXISTS (SELECT 1 FROM customer_goal_previews p '
            'WHERE p.id=NEW.confirmed_preview_id AND p.goal_id=NEW.goal_id AND '
            "p.revision=NEW.goal_revision)) BEGIN SELECT RAISE(ABORT,'planning binding mismatch'); "
            'END',
            'CREATE TRIGGER planning_input_revisions_immutable BEFORE UPDATE ON '
            "planning_input_revisions BEGIN SELECT RAISE(ABORT,'immutable planning history'); END",
            '\n'
            'CREATE TABLE planning_document_versions (\n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\tplan_id VARCHAR(32) NOT NULL, \n'
            '\tversion INTEGER NOT NULL, \n'
            '\tinput_revision INTEGER NOT NULL, \n'
            '\tparent_digest VARCHAR(64), \n'
            '\tdigest VARCHAR(64) NOT NULL, \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tgenerator_version VARCHAR(2000) NOT NULL, \n'
            '\tpolicy_version VARCHAR(2000) NOT NULL, \n'
            '\tactor_id VARCHAR(32) NOT NULL, \n'
            '\tgenerated_at DATETIME NOT NULL, \n'
            '\tvalid_until DATETIME NOT NULL, \n'
            '\tprivacy_revision INTEGER NOT NULL, \n'
            '\tPRIMARY KEY (workspace_id, plan_id, version), \n'
            '\tFOREIGN KEY(workspace_id, plan_id) REFERENCES planning_documents (workspace_id, id) '
            'ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(workspace_id, plan_id, input_revision) REFERENCES '
            'planning_input_revisions (workspace_id, plan_id, revision) ON DELETE RESTRICT, \n'
            '\tCONSTRAINT ck_planning_version CHECK (version >= 1 AND privacy_revision >= 0)\n'
            ')\n'
            '\n',
            'CREATE TRIGGER planning_document_versions_immutable BEFORE UPDATE ON '
            "planning_document_versions BEGIN SELECT RAISE(ABORT,'immutable planning history'); "
            'END',
            '\n'
            'CREATE TABLE planning_document_dependencies (\n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\tplan_id VARCHAR(32) NOT NULL, \n'
            '\tversion INTEGER NOT NULL, \n'
            '\tevidence_key VARCHAR(96) NOT NULL, \n'
            '\taccount_id INTEGER, \n'
            '\tconnection_id INTEGER, \n'
            '\tstore_id VARCHAR(32), \n'
            '\tkind VARCHAR(32) NOT NULL, \n'
            '\tsource_binding_digest VARCHAR(64) NOT NULL, \n'
            '\tdocument_digest VARCHAR(64) NOT NULL, \n'
            '\tsource_revision VARCHAR(160) NOT NULL, \n'
            '\tobserved_at DATETIME NOT NULL, \n'
            '\texpires_at DATETIME NOT NULL, \n'
            '\tprivacy_revision INTEGER NOT NULL, \n'
            '\tPRIMARY KEY (workspace_id, plan_id, version, evidence_key), \n'
            '\tFOREIGN KEY(workspace_id, plan_id, version) REFERENCES planning_document_versions '
            '(workspace_id, plan_id, version) ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(account_id, workspace_id, connection_id) REFERENCES '
            'advertising_accounts (id, workspace_id, connection_id) ON DELETE RESTRICT, \n'
            '\tFOREIGN KEY(store_id, workspace_id) REFERENCES commerce_stores (id, workspace_id) '
            'ON DELETE RESTRICT, \n'
            '\tCONSTRAINT ck_planning_dependency_account CHECK ((account_id IS NULL) = '
            '(connection_id IS NULL)), \n'
            '\tCONSTRAINT ck_planning_dependency_privacy CHECK (privacy_revision >= 0)\n'
            ')\n'
            '\n',
            'CREATE TRIGGER planning_document_dependencies_immutable BEFORE UPDATE ON '
            "planning_document_dependencies BEGIN SELECT RAISE(ABORT,'immutable planning "
            "history'); END",
            '\n'
            'CREATE TABLE planning_document_events (\n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\tplan_id VARCHAR(32) NOT NULL, \n'
            '\tsequence INTEGER NOT NULL, \n'
            '\tevent_id VARCHAR(32) NOT NULL, \n'
            '\tversion INTEGER NOT NULL, \n'
            '\taction_key VARCHAR(96) NOT NULL, \n'
            '\taction_digest VARCHAR(64) NOT NULL, \n'
            '\tkind VARCHAR(16) NOT NULL, \n'
            '\tactor_id VARCHAR(32) NOT NULL, \n'
            '\trecorded_at DATETIME NOT NULL, \n'
            '\tprior_sequence INTEGER, \n'
            '\tcanonical_json TEXT NOT NULL, \n'
            '\tdigest VARCHAR(64) NOT NULL, \n'
            '\tPRIMARY KEY (workspace_id, plan_id, sequence), \n'
            '\tFOREIGN KEY(workspace_id, plan_id, version) REFERENCES planning_document_versions '
            '(workspace_id, plan_id, version) ON DELETE CASCADE, \n'
            '\tCONSTRAINT uq_planning_event_id UNIQUE (workspace_id, event_id), \n'
            '\tFOREIGN KEY(workspace_id, plan_id, prior_sequence) REFERENCES '
            'planning_document_events (workspace_id, plan_id, sequence) ON DELETE RESTRICT, \n'
            '\tCONSTRAINT ck_planning_event_order CHECK (sequence >= 1 AND (prior_sequence IS NULL '
            'OR prior_sequence < sequence)), \n'
            '\tCONSTRAINT ck_planning_event_kind CHECK (kind IN '
            "('decision','assertion','observation'))\n"
            ')\n'
            '\n',
            'CREATE TRIGGER planning_document_events_binding BEFORE INSERT ON '
            'planning_document_events WHEN NOT (NEW.prior_sequence IS NULL OR EXISTS (SELECT 1 '
            'FROM planning_document_events p WHERE p.workspace_id=NEW.workspace_id AND '
            'p.plan_id=NEW.plan_id AND p.sequence=NEW.prior_sequence AND p.version=NEW.version AND '
            "p.action_key=NEW.action_key AND p.kind=NEW.kind)) BEGIN SELECT RAISE(ABORT,'planning "
            "binding mismatch'); END",
            'CREATE TRIGGER planning_document_events_immutable BEFORE UPDATE ON '
            "planning_document_events BEGIN SELECT RAISE(ABORT,'immutable planning history'); END",
            '\n'
            'CREATE TABLE planning_document_requests (\n'
            '\tworkspace_id INTEGER NOT NULL, \n'
            '\tactor_id VARCHAR(32) NOT NULL, \n'
            '\toperation VARCHAR(32) NOT NULL, \n'
            '\trequest_key VARCHAR(128) NOT NULL, \n'
            '\trequest_digest VARCHAR(64) NOT NULL, \n'
            '\tplan_id VARCHAR(32) NOT NULL, \n'
            '\tresult_kind VARCHAR(16) NOT NULL, \n'
            '\tinput_revision INTEGER, \n'
            '\tversion INTEGER, \n'
            '\tevent_sequence INTEGER, \n'
            '\tPRIMARY KEY (workspace_id, actor_id, operation, request_key), \n'
            '\tFOREIGN KEY(workspace_id, plan_id) REFERENCES planning_documents (workspace_id, id) '
            'ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(workspace_id, plan_id, input_revision) REFERENCES '
            'planning_input_revisions (workspace_id, plan_id, revision) ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(workspace_id, plan_id, version) REFERENCES planning_document_versions '
            '(workspace_id, plan_id, version) ON DELETE CASCADE, \n'
            '\tFOREIGN KEY(workspace_id, plan_id, event_sequence) REFERENCES '
            'planning_document_events (workspace_id, plan_id, sequence) ON DELETE CASCADE, \n'
            "\tCONSTRAINT ck_planning_request_result CHECK ((result_kind = 'input' AND "
            'input_revision IS NOT NULL AND version IS NULL AND event_sequence IS NULL) OR '
            "(result_kind = 'version' AND version IS NOT NULL AND input_revision IS NULL AND "
            "event_sequence IS NULL) OR (result_kind = 'event' AND event_sequence IS NOT NULL AND "
            'input_revision IS NULL AND version IS NULL))\n'
            ')\n'
            '\n',
            'CREATE TRIGGER planning_document_requests_immutable BEFORE UPDATE ON '
            "planning_document_requests BEGIN SELECT RAISE(ABORT,'immutable planning history'); "
            'END')}
