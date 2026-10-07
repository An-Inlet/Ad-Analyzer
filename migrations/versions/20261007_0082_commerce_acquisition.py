# ruff: noqa: E501
"""Owned resumable Shopify acquisition; private staging, never qualified evidence."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_0082"
down_revision = "20261007_0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    connection = op.get_bind()
    for table in TABLES:
        if connection.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM " + table + ")")):
            raise RuntimeError("cannot discard acquisition work or private staging")
    for name, table in TRIGGERS:
        suffix = " ON " + table if connection.dialect.name == "postgresql" else ""
        op.execute("DROP TRIGGER IF EXISTS " + name + suffix)
        if connection.dialect.name == "postgresql":
            op.execute("DROP FUNCTION IF EXISTS " + name + "_fn()")
    for table in reversed(TABLES):
        op.drop_table(table)


# Frozen DDL; no imports of evolving application declarations or guards.
TABLES = (
    "commerce_acquisition_jobs",
    "commerce_acquisition_checkpoints",
    "commerce_acquisition_seen",
)
TRIGGERS = (
    ("acq_erase_user", "customer_users"),
    ("acq_erase_membership", "customer_memberships"),
    ("acq_erase_integration", "workspace_integrations"),
    ("acq_erase_store", "commerce_stores"),
    ("acq_job_insert", "commerce_acquisition_jobs"),
    ("acq_job_immutable", "commerce_acquisition_jobs"),
    ("acq_checkpoint_insert", "commerce_acquisition_checkpoints"),
    ("acq_checkpoint_update", "commerce_acquisition_checkpoints"),
    ("acq_erase_workspace", "workspaces"),
    ("acq_erase_session", "customer_sessions"),
    ("acq_erase_source", "shopify_connections"),
    ("acq_erase_privacy", "commerce_evidence_states"),
    ("acq_erase_goal", "customer_goals"),
)
SQL = {
    "postgresql": (
        "\n"
        "CREATE TABLE commerce_acquisition_jobs (\n"
        "\tid VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\tstore_id VARCHAR(32) NOT NULL, \n"
        "\tnative_connection_id INTEGER NOT NULL, \n"
        "\tintegration_id INTEGER NOT NULL, \n"
        "\tgoal_id VARCHAR(32) NOT NULL, \n"
        "\tgoal_revision INTEGER NOT NULL, \n"
        "\tactor_id VARCHAR(32) NOT NULL, \n"
        "\tsession_digest VARCHAR(64) NOT NULL, \n"
        "\tauthenticated_at BIGINT NOT NULL, \n"
        "\tidentity_digest VARCHAR(64) NOT NULL, \n"
        "\tenvironment VARCHAR(16) NOT NULL, \n"
        "\trequest JSON NOT NULL, \n"
        "\trequest_digest VARCHAR(64) NOT NULL, \n"
        "\tprofile JSON NOT NULL, \n"
        "\tprofile_digest VARCHAR(64) NOT NULL, \n"
        "\tstate VARCHAR(16) NOT NULL, \n"
        "\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n"
        "\tdeadline_at TIMESTAMP WITH TIME ZONE NOT NULL, \n"
        "\tstarted_at TIMESTAMP WITH TIME ZONE, \n"
        "\tdue_at TIMESTAMP WITH TIME ZONE NOT NULL, \n"
        "\tlast_served_at TIMESTAMP WITH TIME ZONE, \n"
        "\tlease_token VARCHAR(32), \n"
        "\tlease_until TIMESTAMP WITH TIME ZONE, \n"
        "\tstep_sequence INTEGER NOT NULL, \n"
        "\trequest_attempts INTEGER NOT NULL, \n"
        "\trequests_completed INTEGER NOT NULL, \n"
        "\tcharged_bytes BIGINT NOT NULL, \n"
        "\tresponse_bytes BIGINT NOT NULL, \n"
        "\terror_code VARCHAR(64), \n"
        "\tpublication_id VARCHAR(32), \n"
        "\tterminal_at TIMESTAMP WITH TIME ZONE, \n"
        "\tcleanup_at TIMESTAMP WITH TIME ZONE, \n"
        "\tPRIMARY KEY (id), \n"
        "\tCONSTRAINT uq_acquisition_job_owner UNIQUE (id, workspace_id), \n"
        "\tFOREIGN KEY(store_id, workspace_id) REFERENCES commerce_stores (id, "
        "workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(native_connection_id, workspace_id) REFERENCES "
        "shopify_connections (id, workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(integration_id, workspace_id) REFERENCES "
        "workspace_integrations (id, workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(goal_id, workspace_id) REFERENCES customer_goals (id, "
        "workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(goal_id, goal_revision) REFERENCES customer_goal_revisions "
        "(goal_id, revision) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(publication_id, workspace_id) REFERENCES "
        "commerce_measurement_publications (id, workspace_id) ON DELETE CASCADE, \n"
        "\tCONSTRAINT ck_acquisition_job_state CHECK (state IN "
        "('pending','running','completed','unavailable','cancelled','expired')), \n"
        "\tCONSTRAINT ck_acquisition_environment CHECK (environment IN "
        "('live','contract_test')), \n"
        "\tCONSTRAINT ck_acquisition_time CHECK (deadline_at > created_at AND "
        "(started_at IS NULL OR (started_at >= created_at AND started_at < "
        "deadline_at))), \n"
        "\tCONSTRAINT ck_acquisition_counts CHECK (step_sequence >= 0 AND "
        "request_attempts >= 0 AND requests_completed >= 0 AND requests_completed <= "
        "request_attempts AND charged_bytes >= response_bytes AND response_bytes >= "
        "0), \n"
        "\tCONSTRAINT ck_acquisition_result CHECK ((state = 'completed' AND "
        "publication_id IS NOT NULL) OR (state <> 'completed' AND publication_id IS "
        "NULL)), \n"
        "\tCONSTRAINT ck_acquisition_lease CHECK ((lease_token IS NULL AND "
        "lease_until IS NULL) OR (lease_token IS NOT NULL AND lease_until IS NOT NULL "
        "AND state = 'running')), \n"
        "\tFOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(actor_id) REFERENCES customer_users (id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(session_digest) REFERENCES customer_sessions (digest) ON "
        "DELETE CASCADE\n"
        ")\n"
        "\n",
        "\n"
        "CREATE TABLE commerce_acquisition_checkpoints (\n"
        "\tjob_id VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\tphase VARCHAR(24) NOT NULL, \n"
        "\tsequence INTEGER NOT NULL, \n"
        "\tstate_document JSON NOT NULL, \n"
        "\tstate_digest VARCHAR(64) NOT NULL, \n"
        "\tencrypted_handles TEXT NOT NULL, \n"
        "\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n"
        "\tPRIMARY KEY (job_id), \n"
        "\tFOREIGN KEY(job_id, workspace_id) REFERENCES commerce_acquisition_jobs "
        "(id, workspace_id) ON DELETE CASCADE, \n"
        "\tCONSTRAINT ck_acquisition_phase CHECK (phase IN "
        "('authority_before','order_page','agreement_page','sale_page','order_check','authority_after','publish')), \n"
        "\tCONSTRAINT ck_acquisition_sequence CHECK (sequence >= 0), \n"
        "\tCONSTRAINT ck_acquisition_handle_size CHECK (length(encrypted_handles) <= "
        "16384)\n"
        ")\n"
        "\n",
        "\n"
        "CREATE TABLE commerce_acquisition_seen (\n"
        "\tjob_id VARCHAR(32) NOT NULL, \n"
        "\tkind VARCHAR(16) NOT NULL, \n"
        "\tidentity_digest VARCHAR(64) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\tPRIMARY KEY (job_id, kind, identity_digest), \n"
        "\tFOREIGN KEY(job_id, workspace_id) REFERENCES commerce_acquisition_jobs "
        "(id, workspace_id) ON DELETE CASCADE, \n"
        "\tCONSTRAINT ck_acquisition_seen_kind CHECK (kind IN "
        "('order','agreement','sale','cursor'))\n"
        ")\n"
        "\n",
        "CREATE INDEX ix_acquisition_due ON commerce_acquisition_jobs (state, due_at, "
        "last_served_at)",
        "CREATE UNIQUE INDEX uq_acquisition_active_store ON commerce_acquisition_jobs "
        "(workspace_id, store_id) WHERE state IN ('pending','running')",
        "CREATE OR REPLACE FUNCTION acq_job_insert_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN IF NOT COALESCE((EXISTS(SELECT 1 FROM "
        "shopify_connections n JOIN commerce_stores s ON s.id=NEW.store_id AND "
        "s.workspace_id=NEW.workspace_id JOIN customer_sessions a ON "
        "a.digest=NEW.session_digest JOIN customer_goal_revisions g ON "
        "g.goal_id=NEW.goal_id AND g.revision=NEW.goal_revision WHERE "
        "n.id=NEW.native_connection_id AND n.workspace_id=NEW.workspace_id AND "
        "n.commerce_store_id=s.id AND n.workspace_integration_id=NEW.integration_id "
        "AND s.connection_id=NEW.integration_id AND a.user_id=NEW.actor_id AND "
        "a.authenticated_at=NEW.authenticated_at AND g.workspace_id=NEW.workspace_id) "
        "AND (NEW.request::jsonb #>> '{acquisition_id}')=NEW.id AND "
        "(NEW.request::jsonb #>> '{scope,store_id}')=NEW.store_id AND "
        "(NEW.request::jsonb #>> '{scope,goal_id}')=NEW.goal_id AND "
        "CAST((NEW.request::jsonb #>> '{scope,workspace_id}') AS "
        "BIGINT)=NEW.workspace_id AND CAST((NEW.request::jsonb #>> "
        "'{scope,goal_revision}') AS BIGINT)=NEW.goal_revision AND "
        "CAST((NEW.request::jsonb #>> '{connection_id}') AS "
        "BIGINT)=NEW.integration_id), FALSE) THEN RAISE EXCEPTION 'invalid "
        "acquisition binding'; END IF; RETURN NEW; END; $$",
        "DROP TRIGGER IF EXISTS acq_job_insert ON commerce_acquisition_jobs",
        "CREATE TRIGGER acq_job_insert BEFORE INSERT ON commerce_acquisition_jobs FOR "
        "EACH ROW EXECUTE FUNCTION acq_job_insert_fn()",
        "CREATE OR REPLACE FUNCTION acq_job_immutable_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN IF NOT (CAST(NEW.id AS TEXT) IS NOT DISTINCT FROM "
        "CAST(OLD.id AS TEXT) AND CAST(NEW.workspace_id AS TEXT) IS NOT DISTINCT FROM "
        "CAST(OLD.workspace_id AS TEXT) AND CAST(NEW.store_id AS TEXT) IS NOT "
        "DISTINCT FROM CAST(OLD.store_id AS TEXT) AND CAST(NEW.native_connection_id "
        "AS TEXT) IS NOT DISTINCT FROM CAST(OLD.native_connection_id AS TEXT) AND "
        "CAST(NEW.integration_id AS TEXT) IS NOT DISTINCT FROM "
        "CAST(OLD.integration_id AS TEXT) AND CAST(NEW.goal_id AS TEXT) IS NOT "
        "DISTINCT FROM CAST(OLD.goal_id AS TEXT) AND CAST(NEW.goal_revision AS TEXT) "
        "IS NOT DISTINCT FROM CAST(OLD.goal_revision AS TEXT) AND CAST(NEW.actor_id "
        "AS TEXT) IS NOT DISTINCT FROM CAST(OLD.actor_id AS TEXT) AND "
        "CAST(NEW.session_digest AS TEXT) IS NOT DISTINCT FROM "
        "CAST(OLD.session_digest AS TEXT) AND CAST(NEW.authenticated_at AS TEXT) IS "
        "NOT DISTINCT FROM CAST(OLD.authenticated_at AS TEXT) AND "
        "CAST(NEW.identity_digest AS TEXT) IS NOT DISTINCT FROM "
        "CAST(OLD.identity_digest AS TEXT) AND CAST(NEW.environment AS TEXT) IS NOT "
        "DISTINCT FROM CAST(OLD.environment AS TEXT) AND CAST(NEW.request AS TEXT) IS "
        "NOT DISTINCT FROM CAST(OLD.request AS TEXT) AND CAST(NEW.request_digest AS "
        "TEXT) IS NOT DISTINCT FROM CAST(OLD.request_digest AS TEXT) AND "
        "CAST(NEW.profile AS TEXT) IS NOT DISTINCT FROM CAST(OLD.profile AS TEXT) AND "
        "CAST(NEW.profile_digest AS TEXT) IS NOT DISTINCT FROM "
        "CAST(OLD.profile_digest AS TEXT) AND CAST(NEW.created_at AS TEXT) IS NOT "
        "DISTINCT FROM CAST(OLD.created_at AS TEXT) AND CAST(NEW.deadline_at AS TEXT) "
        "IS NOT DISTINCT FROM CAST(OLD.deadline_at AS TEXT)) OR (OLD.started_at IS "
        "NOT NULL AND (NEW.started_at IS NULL OR NEW.started_at<>OLD.started_at)) "
        "THEN RAISE EXCEPTION 'invalid acquisition binding'; END IF; RETURN NEW; END; "
        "$$",
        "DROP TRIGGER IF EXISTS acq_job_immutable ON commerce_acquisition_jobs",
        "CREATE TRIGGER acq_job_immutable BEFORE UPDATE ON commerce_acquisition_jobs "
        "FOR EACH ROW EXECUTE FUNCTION acq_job_immutable_fn()",
        "CREATE OR REPLACE FUNCTION acq_checkpoint_insert_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF NOT COALESCE((EXISTS(SELECT 1 FROM "
        "commerce_acquisition_jobs j WHERE j.id=NEW.job_id AND "
        "j.workspace_id=NEW.workspace_id AND j.state IN ('pending','running') AND "
        "j.step_sequence=NEW.sequence AND (NEW.state_document::jsonb #>> "
        "'{request_digest}')=j.request_digest AND (NEW.state_document::jsonb #>> "
        "'{profile_digest}')=j.profile_digest) AND (NEW.state_document::jsonb #>> "
        "'{phase}')=NEW.phase AND CAST((NEW.state_document::jsonb #>> '{sequence}') "
        "AS BIGINT)=NEW.sequence AND length(CAST(NEW.state_document AS "
        "TEXT))<=131072), FALSE) THEN RAISE EXCEPTION 'invalid acquisition binding'; "
        "END IF; RETURN NEW; END; $$",
        "DROP TRIGGER IF EXISTS acq_checkpoint_insert ON commerce_acquisition_checkpoints",
        "CREATE TRIGGER acq_checkpoint_insert BEFORE INSERT ON "
        "commerce_acquisition_checkpoints FOR EACH ROW EXECUTE FUNCTION "
        "acq_checkpoint_insert_fn()",
        "CREATE OR REPLACE FUNCTION acq_checkpoint_update_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF NOT COALESCE((EXISTS(SELECT 1 FROM "
        "commerce_acquisition_jobs j WHERE j.id=NEW.job_id AND "
        "j.workspace_id=NEW.workspace_id AND j.state IN ('pending','running') AND "
        "j.step_sequence=NEW.sequence AND (NEW.state_document::jsonb #>> "
        "'{request_digest}')=j.request_digest AND (NEW.state_document::jsonb #>> "
        "'{profile_digest}')=j.profile_digest) AND (NEW.state_document::jsonb #>> "
        "'{phase}')=NEW.phase AND CAST((NEW.state_document::jsonb #>> '{sequence}') "
        "AS BIGINT)=NEW.sequence AND length(CAST(NEW.state_document AS "
        "TEXT))<=131072), FALSE) THEN RAISE EXCEPTION 'invalid acquisition binding'; "
        "END IF; RETURN NEW; END; $$",
        "DROP TRIGGER IF EXISTS acq_checkpoint_update ON commerce_acquisition_checkpoints",
        "CREATE TRIGGER acq_checkpoint_update BEFORE UPDATE ON "
        "commerce_acquisition_checkpoints FOR EACH ROW EXECUTE FUNCTION "
        "acq_checkpoint_update_fn()",
        "CREATE OR REPLACE FUNCTION acq_erase_user_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN IF NEW.status <> 'active' THEN DELETE FROM "
        "commerce_acquisition_jobs WHERE actor_id=NEW.id; END IF; RETURN NEW; END; $$",
        "DROP TRIGGER IF EXISTS acq_erase_user ON customer_users",
        "CREATE TRIGGER acq_erase_user AFTER UPDATE ON customer_users FOR EACH ROW "
        "EXECUTE FUNCTION acq_erase_user_fn()",
        "CREATE OR REPLACE FUNCTION acq_erase_membership_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF NEW.status <> 'active' OR NEW.role <> "
        "'owner' THEN DELETE FROM commerce_acquisition_jobs WHERE "
        "actor_id=NEW.user_id AND workspace_id=NEW.workspace_id; END IF; RETURN NEW; "
        "END; $$",
        "DROP TRIGGER IF EXISTS acq_erase_membership ON customer_memberships",
        "CREATE TRIGGER acq_erase_membership AFTER UPDATE ON customer_memberships FOR "
        "EACH ROW EXECUTE FUNCTION acq_erase_membership_fn()",
        "CREATE OR REPLACE FUNCTION acq_erase_integration_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF NEW.status <> 'active' THEN DELETE FROM "
        "commerce_acquisition_jobs WHERE integration_id=NEW.id AND "
        "workspace_id=NEW.workspace_id; END IF; RETURN NEW; END; $$",
        "DROP TRIGGER IF EXISTS acq_erase_integration ON workspace_integrations",
        "CREATE TRIGGER acq_erase_integration AFTER UPDATE ON workspace_integrations "
        "FOR EACH ROW EXECUTE FUNCTION acq_erase_integration_fn()",
        "CREATE OR REPLACE FUNCTION acq_erase_store_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN IF NEW.status <> 'active' OR NEW.revision<>OLD.revision "
        "THEN DELETE FROM commerce_acquisition_jobs WHERE store_id=NEW.id AND "
        "workspace_id=NEW.workspace_id; END IF; RETURN NEW; END; $$",
        "DROP TRIGGER IF EXISTS acq_erase_store ON commerce_stores",
        "CREATE TRIGGER acq_erase_store AFTER UPDATE ON commerce_stores FOR EACH ROW "
        "EXECUTE FUNCTION acq_erase_store_fn()",
        "CREATE OR REPLACE FUNCTION acq_erase_workspace_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN IF NEW.status <> 'active' OR NEW.export_privacy_revision "
        "<> OLD.export_privacy_revision THEN DELETE FROM commerce_acquisition_jobs "
        "WHERE workspace_id=NEW.id; END IF; RETURN NEW; END; $$",
        "DROP TRIGGER IF EXISTS acq_erase_workspace ON workspaces",
        "CREATE TRIGGER acq_erase_workspace AFTER UPDATE ON workspaces FOR EACH ROW "
        "EXECUTE FUNCTION acq_erase_workspace_fn()",
        "CREATE OR REPLACE FUNCTION acq_erase_session_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN IF NEW.revoked_at IS NOT NULL OR "
        "NEW.authenticated_at<>OLD.authenticated_at OR NEW.user_id<>OLD.user_id THEN "
        "DELETE FROM commerce_acquisition_jobs WHERE session_digest=NEW.digest; END "
        "IF; RETURN NEW; END; $$",
        "DROP TRIGGER IF EXISTS acq_erase_session ON customer_sessions",
        "CREATE TRIGGER acq_erase_session AFTER UPDATE ON customer_sessions FOR EACH "
        "ROW EXECUTE FUNCTION acq_erase_session_fn()",
        "CREATE OR REPLACE FUNCTION acq_erase_source_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN IF NEW.status <> 'connected' OR "
        "NEW.connected_at<>OLD.connected_at OR "
        "NEW.encrypted_credentials<>OLD.encrypted_credentials THEN DELETE FROM "
        "commerce_acquisition_jobs WHERE native_connection_id=NEW.id AND "
        "workspace_id=NEW.workspace_id; END IF; RETURN NEW; END; $$",
        "DROP TRIGGER IF EXISTS acq_erase_source ON shopify_connections",
        "CREATE TRIGGER acq_erase_source AFTER UPDATE ON shopify_connections FOR EACH "
        "ROW EXECUTE FUNCTION acq_erase_source_fn()",
        "CREATE OR REPLACE FUNCTION acq_erase_privacy_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN IF NEW.generation<>OLD.generation OR "
        "NEW.privacy_epoch<>OLD.privacy_epoch THEN DELETE FROM "
        "commerce_acquisition_jobs WHERE store_id=NEW.store_id AND "
        "workspace_id=NEW.workspace_id; END IF; RETURN NEW; END; $$",
        "DROP TRIGGER IF EXISTS acq_erase_privacy ON commerce_evidence_states",
        "CREATE TRIGGER acq_erase_privacy AFTER UPDATE ON commerce_evidence_states "
        "FOR EACH ROW EXECUTE FUNCTION acq_erase_privacy_fn()",
        "CREATE OR REPLACE FUNCTION acq_erase_goal_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN IF NEW.revision<>OLD.revision THEN DELETE FROM "
        "commerce_acquisition_jobs WHERE goal_id=NEW.id AND "
        "workspace_id=NEW.workspace_id; END IF; RETURN NEW; END; $$",
        "DROP TRIGGER IF EXISTS acq_erase_goal ON customer_goals",
        "CREATE TRIGGER acq_erase_goal AFTER UPDATE ON customer_goals FOR EACH ROW "
        "EXECUTE FUNCTION acq_erase_goal_fn()",
    ),
    "sqlite": (
        "\n"
        "CREATE TABLE commerce_acquisition_jobs (\n"
        "\tid VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\tstore_id VARCHAR(32) NOT NULL, \n"
        "\tnative_connection_id INTEGER NOT NULL, \n"
        "\tintegration_id INTEGER NOT NULL, \n"
        "\tgoal_id VARCHAR(32) NOT NULL, \n"
        "\tgoal_revision INTEGER NOT NULL, \n"
        "\tactor_id VARCHAR(32) NOT NULL, \n"
        "\tsession_digest VARCHAR(64) NOT NULL, \n"
        "\tauthenticated_at BIGINT NOT NULL, \n"
        "\tidentity_digest VARCHAR(64) NOT NULL, \n"
        "\tenvironment VARCHAR(16) NOT NULL, \n"
        "\trequest JSON NOT NULL, \n"
        "\trequest_digest VARCHAR(64) NOT NULL, \n"
        "\tprofile JSON NOT NULL, \n"
        "\tprofile_digest VARCHAR(64) NOT NULL, \n"
        "\tstate VARCHAR(16) NOT NULL, \n"
        "\tcreated_at DATETIME NOT NULL, \n"
        "\tdeadline_at DATETIME NOT NULL, \n"
        "\tstarted_at DATETIME, \n"
        "\tdue_at DATETIME NOT NULL, \n"
        "\tlast_served_at DATETIME, \n"
        "\tlease_token VARCHAR(32), \n"
        "\tlease_until DATETIME, \n"
        "\tstep_sequence INTEGER NOT NULL, \n"
        "\trequest_attempts INTEGER NOT NULL, \n"
        "\trequests_completed INTEGER NOT NULL, \n"
        "\tcharged_bytes BIGINT NOT NULL, \n"
        "\tresponse_bytes BIGINT NOT NULL, \n"
        "\terror_code VARCHAR(64), \n"
        "\tpublication_id VARCHAR(32), \n"
        "\tterminal_at DATETIME, \n"
        "\tcleanup_at DATETIME, \n"
        "\tPRIMARY KEY (id), \n"
        "\tCONSTRAINT uq_acquisition_job_owner UNIQUE (id, workspace_id), \n"
        "\tFOREIGN KEY(store_id, workspace_id) REFERENCES commerce_stores (id, "
        "workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(native_connection_id, workspace_id) REFERENCES shopify_connections "
        "(id, workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(integration_id, workspace_id) REFERENCES workspace_integrations "
        "(id, workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(goal_id, workspace_id) REFERENCES customer_goals (id, "
        "workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(goal_id, goal_revision) REFERENCES customer_goal_revisions "
        "(goal_id, revision) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(publication_id, workspace_id) REFERENCES "
        "commerce_measurement_publications (id, workspace_id) ON DELETE CASCADE, \n"
        "\tCONSTRAINT ck_acquisition_job_state CHECK (state IN "
        "('pending','running','completed','unavailable','cancelled','expired')), \n"
        "\tCONSTRAINT ck_acquisition_environment CHECK (environment IN "
        "('live','contract_test')), \n"
        "\tCONSTRAINT ck_acquisition_time CHECK (deadline_at > created_at AND (started_at "
        "IS NULL OR (started_at >= created_at AND started_at < deadline_at))), \n"
        "\tCONSTRAINT ck_acquisition_counts CHECK (step_sequence >= 0 AND "
        "request_attempts >= 0 AND requests_completed >= 0 AND requests_completed <= "
        "request_attempts AND charged_bytes >= response_bytes AND response_bytes >= 0), \n"
        "\tCONSTRAINT ck_acquisition_result CHECK ((state = 'completed' AND "
        "publication_id IS NOT NULL) OR (state <> 'completed' AND publication_id IS "
        "NULL)), \n"
        "\tCONSTRAINT ck_acquisition_lease CHECK ((lease_token IS NULL AND lease_until IS "
        "NULL) OR (lease_token IS NOT NULL AND lease_until IS NOT NULL AND state = "
        "'running')), \n"
        "\tFOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(actor_id) REFERENCES customer_users (id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(session_digest) REFERENCES customer_sessions (digest) ON DELETE "
        "CASCADE\n"
        ")\n"
        "\n",
        "\n"
        "CREATE TABLE commerce_acquisition_checkpoints (\n"
        "\tjob_id VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\tphase VARCHAR(24) NOT NULL, \n"
        "\tsequence INTEGER NOT NULL, \n"
        "\tstate_document JSON NOT NULL, \n"
        "\tstate_digest VARCHAR(64) NOT NULL, \n"
        "\tencrypted_handles TEXT NOT NULL, \n"
        "\tupdated_at DATETIME NOT NULL, \n"
        "\tPRIMARY KEY (job_id), \n"
        "\tFOREIGN KEY(job_id, workspace_id) REFERENCES commerce_acquisition_jobs (id, "
        "workspace_id) ON DELETE CASCADE, \n"
        "\tCONSTRAINT ck_acquisition_phase CHECK (phase IN "
        "('authority_before','order_page','agreement_page','sale_page','order_check','authority_after','publish')), \n"
        "\tCONSTRAINT ck_acquisition_sequence CHECK (sequence >= 0), \n"
        "\tCONSTRAINT ck_acquisition_handle_size CHECK (length(encrypted_handles) <= "
        "16384)\n"
        ")\n"
        "\n",
        "\n"
        "CREATE TABLE commerce_acquisition_seen (\n"
        "\tjob_id VARCHAR(32) NOT NULL, \n"
        "\tkind VARCHAR(16) NOT NULL, \n"
        "\tidentity_digest VARCHAR(64) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\tPRIMARY KEY (job_id, kind, identity_digest), \n"
        "\tFOREIGN KEY(job_id, workspace_id) REFERENCES commerce_acquisition_jobs (id, "
        "workspace_id) ON DELETE CASCADE, \n"
        "\tCONSTRAINT ck_acquisition_seen_kind CHECK (kind IN "
        "('order','agreement','sale','cursor'))\n"
        ")\n"
        "\n",
        "CREATE INDEX ix_acquisition_due ON commerce_acquisition_jobs (state, due_at, "
        "last_served_at)",
        "CREATE UNIQUE INDEX uq_acquisition_active_store ON commerce_acquisition_jobs "
        "(workspace_id, store_id) WHERE state IN ('pending','running')",
        "CREATE TRIGGER IF NOT EXISTS acq_job_insert BEFORE INSERT ON "
        "commerce_acquisition_jobs WHEN NOT COALESCE((EXISTS(SELECT 1 FROM "
        "shopify_connections n JOIN commerce_stores s ON s.id=NEW.store_id AND "
        "s.workspace_id=NEW.workspace_id JOIN customer_sessions a ON "
        "a.digest=NEW.session_digest JOIN customer_goal_revisions g ON "
        "g.goal_id=NEW.goal_id AND g.revision=NEW.goal_revision WHERE "
        "n.id=NEW.native_connection_id AND n.workspace_id=NEW.workspace_id AND "
        "n.commerce_store_id=s.id AND n.workspace_integration_id=NEW.integration_id AND "
        "s.connection_id=NEW.integration_id AND a.user_id=NEW.actor_id AND "
        "a.authenticated_at=NEW.authenticated_at AND g.workspace_id=NEW.workspace_id) AND "
        "json_extract(NEW.request, '$.acquisition_id')=NEW.id AND "
        "json_extract(NEW.request, '$.scope.store_id')=NEW.store_id AND "
        "json_extract(NEW.request, '$.scope.goal_id')=NEW.goal_id AND "
        "CAST(json_extract(NEW.request, '$.scope.workspace_id') AS "
        "BIGINT)=NEW.workspace_id AND CAST(json_extract(NEW.request, "
        "'$.scope.goal_revision') AS BIGINT)=NEW.goal_revision AND "
        "CAST(json_extract(NEW.request, '$.connection_id') AS BIGINT)=NEW.integration_id "
        "AND (SELECT foreign_keys FROM pragma_foreign_keys)=1), FALSE) BEGIN SELECT "
        "RAISE(ABORT, 'invalid acquisition binding'); END",
        "CREATE TRIGGER IF NOT EXISTS acq_job_immutable BEFORE UPDATE ON "
        "commerce_acquisition_jobs WHEN NOT (NEW.id IS OLD.id AND NEW.workspace_id IS "
        "OLD.workspace_id AND NEW.store_id IS OLD.store_id AND NEW.native_connection_id "
        "IS OLD.native_connection_id AND NEW.integration_id IS OLD.integration_id AND "
        "NEW.goal_id IS OLD.goal_id AND NEW.goal_revision IS OLD.goal_revision AND "
        "NEW.actor_id IS OLD.actor_id AND NEW.session_digest IS OLD.session_digest AND "
        "NEW.authenticated_at IS OLD.authenticated_at AND NEW.identity_digest IS "
        "OLD.identity_digest AND NEW.environment IS OLD.environment AND NEW.request IS "
        "OLD.request AND NEW.request_digest IS OLD.request_digest AND NEW.profile IS "
        "OLD.profile AND NEW.profile_digest IS OLD.profile_digest AND NEW.created_at IS "
        "OLD.created_at AND NEW.deadline_at IS OLD.deadline_at) OR (OLD.started_at IS NOT "
        "NULL AND (NEW.started_at IS NULL OR NEW.started_at<>OLD.started_at)) BEGIN "
        "SELECT RAISE(ABORT, 'invalid acquisition binding'); END",
        "CREATE TRIGGER IF NOT EXISTS acq_checkpoint_insert BEFORE INSERT ON "
        "commerce_acquisition_checkpoints WHEN NOT COALESCE((EXISTS(SELECT 1 FROM "
        "commerce_acquisition_jobs j WHERE j.id=NEW.job_id AND "
        "j.workspace_id=NEW.workspace_id AND j.state IN ('pending','running') AND "
        "j.step_sequence=NEW.sequence AND json_extract(NEW.state_document, "
        "'$.request_digest')=j.request_digest AND json_extract(NEW.state_document, "
        "'$.profile_digest')=j.profile_digest) AND json_extract(NEW.state_document, "
        "'$.phase')=NEW.phase AND CAST(json_extract(NEW.state_document, '$.sequence') AS "
        "BIGINT)=NEW.sequence AND length(CAST(NEW.state_document AS TEXT))<=131072), "
        "FALSE) BEGIN SELECT RAISE(ABORT, 'invalid acquisition binding'); END",
        "CREATE TRIGGER IF NOT EXISTS acq_checkpoint_update BEFORE UPDATE ON "
        "commerce_acquisition_checkpoints WHEN NOT COALESCE((EXISTS(SELECT 1 FROM "
        "commerce_acquisition_jobs j WHERE j.id=NEW.job_id AND "
        "j.workspace_id=NEW.workspace_id AND j.state IN ('pending','running') AND "
        "j.step_sequence=NEW.sequence AND json_extract(NEW.state_document, "
        "'$.request_digest')=j.request_digest AND json_extract(NEW.state_document, "
        "'$.profile_digest')=j.profile_digest) AND json_extract(NEW.state_document, "
        "'$.phase')=NEW.phase AND CAST(json_extract(NEW.state_document, '$.sequence') AS "
        "BIGINT)=NEW.sequence AND length(CAST(NEW.state_document AS TEXT))<=131072), "
        "FALSE) BEGIN SELECT RAISE(ABORT, 'invalid acquisition binding'); END",
        "CREATE TRIGGER IF NOT EXISTS acq_erase_user AFTER UPDATE ON customer_users WHEN "
        "NEW.status <> 'active' BEGIN DELETE FROM commerce_acquisition_jobs WHERE "
        "actor_id=NEW.id; END",
        "CREATE TRIGGER IF NOT EXISTS acq_erase_membership AFTER UPDATE ON "
        "customer_memberships WHEN NEW.status <> 'active' OR NEW.role <> 'owner' BEGIN "
        "DELETE FROM commerce_acquisition_jobs WHERE actor_id=NEW.user_id AND "
        "workspace_id=NEW.workspace_id; END",
        "CREATE TRIGGER IF NOT EXISTS acq_erase_integration AFTER UPDATE ON "
        "workspace_integrations WHEN NEW.status <> 'active' BEGIN DELETE FROM "
        "commerce_acquisition_jobs WHERE integration_id=NEW.id AND "
        "workspace_id=NEW.workspace_id; END",
        "CREATE TRIGGER IF NOT EXISTS acq_erase_store AFTER UPDATE ON commerce_stores "
        "WHEN NEW.status <> 'active' OR NEW.revision<>OLD.revision BEGIN DELETE FROM "
        "commerce_acquisition_jobs WHERE store_id=NEW.id AND "
        "workspace_id=NEW.workspace_id; END",
        "CREATE TRIGGER IF NOT EXISTS acq_erase_workspace AFTER UPDATE ON workspaces WHEN "
        "NEW.status <> 'active' OR NEW.export_privacy_revision <> "
        "OLD.export_privacy_revision BEGIN DELETE FROM commerce_acquisition_jobs WHERE "
        "workspace_id=NEW.id; END",
        "CREATE TRIGGER IF NOT EXISTS acq_erase_session AFTER UPDATE ON customer_sessions "
        "WHEN NEW.revoked_at IS NOT NULL OR NEW.authenticated_at<>OLD.authenticated_at OR "
        "NEW.user_id<>OLD.user_id BEGIN DELETE FROM commerce_acquisition_jobs WHERE "
        "session_digest=NEW.digest; END",
        "CREATE TRIGGER IF NOT EXISTS acq_erase_source AFTER UPDATE ON "
        "shopify_connections WHEN NEW.status <> 'connected' OR "
        "NEW.connected_at<>OLD.connected_at OR "
        "NEW.encrypted_credentials<>OLD.encrypted_credentials BEGIN DELETE FROM "
        "commerce_acquisition_jobs WHERE native_connection_id=NEW.id AND "
        "workspace_id=NEW.workspace_id; END",
        "CREATE TRIGGER IF NOT EXISTS acq_erase_privacy AFTER UPDATE ON "
        "commerce_evidence_states WHEN NEW.generation<>OLD.generation OR "
        "NEW.privacy_epoch<>OLD.privacy_epoch BEGIN DELETE FROM commerce_acquisition_jobs "
        "WHERE store_id=NEW.store_id AND workspace_id=NEW.workspace_id; END",
        "CREATE TRIGGER IF NOT EXISTS acq_erase_goal AFTER UPDATE ON customer_goals WHEN "
        "NEW.revision<>OLD.revision BEGIN DELETE FROM commerce_acquisition_jobs WHERE "
        "goal_id=NEW.id AND workspace_id=NEW.workspace_id; END",
    ),
}
