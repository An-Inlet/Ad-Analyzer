# ruff: noqa: E501
"""Initial operational opportunity and full evidence dependency ownership."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_0084"
down_revision = "20261007_0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    connection = op.get_bind()
    for table in TABLES:
        if connection.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM " + table + ")")):
            raise RuntimeError("cannot discard retained initial rule lineage")
    for table in reversed(TABLES):
        op.drop_table(table)
        if connection.dialect.name == "postgresql":
            for suffix in ("owner", "immutable", "guard", "erase"):
                op.execute("DROP FUNCTION IF EXISTS " + table + "_" + suffix + "_fn()")


# Frozen DDL, independent of evolving application model/trigger code.
TABLES = (
    "initial_rule_opportunities",
    "initial_rule_admission_origins",
    "initial_rule_candidate_dependencies",
    "initial_rule_candidate_observations",
)

SQL = {
    "postgresql": (
        "\n"
        "CREATE TABLE initial_rule_opportunities (\n"
        "\tid VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\tenvironment VARCHAR(16) NOT NULL, \n"
        "\tledger_id VARCHAR(32) NOT NULL, \n"
        "\tnative_account_identity_digest VARCHAR(64) NOT NULL, \n"
        "\tbudget_owner_identity_digest VARCHAR(64) NOT NULL, \n"
        "\tsemantic_key_digest VARCHAR(64) NOT NULL, \n"
        "\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n"
        "\tpending_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n"
        "\tPRIMARY KEY (id), \n"
        "\tCONSTRAINT uq_initial_rule_opportunity_scope UNIQUE (id, workspace_id), \n"
        "\tCONSTRAINT uq_initial_rule_semantic_key UNIQUE (semantic_key_digest), \n"
        "\tCONSTRAINT uq_initial_rule_native_opportunity UNIQUE (workspace_id, "
        "environment, ledger_id, native_account_identity_digest, "
        "budget_owner_identity_digest), \n"
        "\tFOREIGN KEY(ledger_id, workspace_id, environment) REFERENCES "
        "provider_period_ledgers (id, workspace_id, environment) ON DELETE RESTRICT, \n"
        "\tCONSTRAINT ck_initial_rule_env CHECK (environment IN "
        "('contract_test','live')), \n"
        "\tCONSTRAINT ck_initial_rule_pending_expiry CHECK (pending_expires_at > "
        "created_at)\n"
        ")\n"
        "\n",
        "CREATE INDEX ix_initial_rule_opportunities_pending_expires_at ON "
        "initial_rule_opportunities (pending_expires_at)",
        "CREATE FUNCTION initial_rule_opportunities_owner_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN IF NOT (NEW.id=substr(NEW.semantic_key_digest,1,32) AND "
        "length(NEW.semantic_key_digest)=64 AND "
        "length(NEW.native_account_identity_digest)=64 AND "
        "length(NEW.budget_owner_identity_digest)=64) THEN RAISE EXCEPTION 'owned initial "
        "rule lineage required'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER initial_rule_opportunities_owner BEFORE INSERT ON "
        "initial_rule_opportunities FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_opportunities_owner_fn()",
        "CREATE FUNCTION initial_rule_opportunities_immutable_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable initial rule lineage'; "
        "END; $$",
        "CREATE TRIGGER initial_rule_opportunities_immutable BEFORE UPDATE ON "
        "initial_rule_opportunities FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_opportunities_immutable_fn()",
        "CREATE FUNCTION initial_rule_opportunities_guard_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR "
        "UPDATE NOWAIT; RETURN OLD; END; $$",
        "CREATE TRIGGER initial_rule_opportunities_guard BEFORE DELETE ON "
        "initial_rule_opportunities FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_opportunities_guard_fn()",
        "CREATE FUNCTION initial_rule_opportunities_erase_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN UPDATE workspaces SET "
        "export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND "
        "OLD.pending_expires_at > clock_timestamp(); RETURN NULL; END; $$",
        "CREATE TRIGGER initial_rule_opportunities_erase AFTER DELETE ON "
        "initial_rule_opportunities FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_opportunities_erase_fn()",
        "\n"
        "CREATE TABLE initial_rule_admission_origins (\n"
        "\tadmission_id VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\topportunity_id VARCHAR(32) NOT NULL, \n"
        "\tPRIMARY KEY (admission_id), \n"
        "\tFOREIGN KEY(admission_id, workspace_id) REFERENCES provider_automatic_decisions "
        "(id, workspace_id) ON DELETE RESTRICT, \n"
        "\tFOREIGN KEY(opportunity_id, workspace_id) REFERENCES initial_rule_opportunities "
        "(id, workspace_id) ON DELETE RESTRICT, \n"
        "\tCONSTRAINT uq_initial_rule_consumed_once UNIQUE (opportunity_id)\n"
        ")\n"
        "\n",
        "CREATE FUNCTION initial_rule_admission_origins_owner_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF NOT (EXISTS(SELECT 1 FROM "
        "provider_automatic_decisions a JOIN initial_rule_opportunities o ON "
        "o.id=NEW.opportunity_id JOIN initial_rule_candidate_dependencies d ON "
        "d.opportunity_id=o.id JOIN optimization_candidate_results r ON "
        "r.job_id=d.candidate_job_id WHERE a.id=NEW.admission_id AND "
        "a.workspace_id=NEW.workspace_id AND o.workspace_id=NEW.workspace_id AND "
        "a.ledger_id=o.ledger_id AND a.environment=o.environment AND "
        "a.account_identity_digest=o.native_account_identity_digest AND "
        "r.workspace_id=a.workspace_id AND r.decision_digest=a.candidate_digest AND "
        "r.evidence_digest=a.evidence_digest AND r.decision #>> "
        "'{scope,budget_owner_key}'=a.budget_owner_key AND r.decision #>> "
        "'{evidence,source_reference}'=o.id AND r.decision #>> "
        "'{evidence,basis,semantic_key_digest}'=o.semantic_key_digest AND r.decision #>> "
        "'{status}'='suggested' AND r.decision #>> "
        "'{schema_version}'='inlet.initial-reported-rule-candidate.v1')) THEN RAISE "
        "EXCEPTION 'owned initial rule lineage required'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER initial_rule_admission_origins_owner BEFORE INSERT ON "
        "initial_rule_admission_origins FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_admission_origins_owner_fn()",
        "CREATE FUNCTION initial_rule_admission_origins_immutable_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable initial rule lineage'; "
        "END; $$",
        "CREATE TRIGGER initial_rule_admission_origins_immutable BEFORE UPDATE ON "
        "initial_rule_admission_origins FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_admission_origins_immutable_fn()",
        "CREATE FUNCTION initial_rule_admission_origins_guard_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'protected initial rule admission'; "
        "END; $$",
        "CREATE TRIGGER initial_rule_admission_origins_guard BEFORE DELETE ON "
        "initial_rule_admission_origins FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_admission_origins_guard_fn()",
        "\n"
        "CREATE TABLE initial_rule_candidate_dependencies (\n"
        "\tcandidate_job_id VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\taccount_id INTEGER NOT NULL, \n"
        "\tcampaign_id INTEGER NOT NULL, \n"
        "\topportunity_id VARCHAR(32) NOT NULL, \n"
        "\tpreview_id VARCHAR(32) NOT NULL, \n"
        "\tcalibration_id VARCHAR(32) NOT NULL, \n"
        "\tselected_observation_id VARCHAR(32) NOT NULL, \n"
        "\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n"
        "\tPRIMARY KEY (candidate_job_id), \n"
        "\tCONSTRAINT uq_initial_rule_dependency_scope UNIQUE (candidate_job_id, "
        "workspace_id, account_id, campaign_id), \n"
        "\tFOREIGN KEY(candidate_job_id, workspace_id) REFERENCES "
        "optimization_candidate_jobs (id, workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(opportunity_id, workspace_id) REFERENCES initial_rule_opportunities "
        "(id, workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(preview_id, workspace_id, account_id, campaign_id) REFERENCES "
        "initial_plan_previews (id, workspace_id, account_id, campaign_id) ON DELETE "
        "CASCADE, \n"
        "\tFOREIGN KEY(calibration_id, workspace_id, account_id, campaign_id) REFERENCES "
        "initial_calibration_runs (id, workspace_id, account_id, campaign_id) ON DELETE "
        "CASCADE, \n"
        "\tFOREIGN KEY(selected_observation_id, workspace_id, account_id, campaign_id) "
        "REFERENCES initial_observations (id, workspace_id, account_id, campaign_id) ON "
        "DELETE CASCADE\n"
        ")\n"
        "\n",
        "CREATE INDEX ix_initial_rule_candidate_dependencies_expires_at ON "
        "initial_rule_candidate_dependencies (expires_at)",
        "CREATE INDEX ix_initial_rule_candidate_dependencies_opportunity_id ON "
        "initial_rule_candidate_dependencies (opportunity_id)",
        "CREATE FUNCTION initial_rule_candidate_dependencies_owner_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF NOT (EXISTS(SELECT 1 FROM initial_plan_previews p "
        "JOIN initial_calibration_runs c ON c.id=p.calibration_id JOIN "
        "optimization_candidate_jobs j ON j.id=NEW.candidate_job_id JOIN "
        "initial_rule_opportunities o ON o.id=NEW.opportunity_id WHERE p.id=NEW.preview_id "
        "AND p.workspace_id=NEW.workspace_id AND p.account_id=NEW.account_id AND "
        "p.campaign_id=NEW.campaign_id AND p.calibration_id=NEW.calibration_id AND "
        "p.observation_id=NEW.selected_observation_id AND j.workspace_id=p.workspace_id "
        "AND j.actor_id=p.original_actor_id AND "
        "j.auth_session_digest=p.original_session_digest AND j.environment=c.environment "
        "AND o.environment=c.environment AND o.workspace_id=p.workspace_id AND "
        "j.attempt_id IS NULL AND NEW.expires_at<=p.expires_at AND "
        "NEW.expires_at<=c.expires_at AND NEW.expires_at<=o.pending_expires_at)) THEN "
        "RAISE EXCEPTION 'owned initial rule lineage required'; END IF; RETURN NEW; END; "
        "$$",
        "CREATE TRIGGER initial_rule_candidate_dependencies_owner BEFORE INSERT ON "
        "initial_rule_candidate_dependencies FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_candidate_dependencies_owner_fn()",
        "CREATE FUNCTION initial_rule_candidate_dependencies_immutable_fn() RETURNS "
        "trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable initial rule "
        "lineage'; END; $$",
        "CREATE TRIGGER initial_rule_candidate_dependencies_immutable BEFORE UPDATE ON "
        "initial_rule_candidate_dependencies FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_candidate_dependencies_immutable_fn()",
        "CREATE FUNCTION initial_rule_candidate_dependencies_guard_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id "
        "FOR UPDATE NOWAIT; RETURN OLD; END; $$",
        "CREATE TRIGGER initial_rule_candidate_dependencies_guard BEFORE DELETE ON "
        "initial_rule_candidate_dependencies FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_candidate_dependencies_guard_fn()",
        "CREATE FUNCTION initial_rule_candidate_dependencies_erase_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN DELETE FROM optimization_candidate_jobs WHERE "
        "id=OLD.candidate_job_id AND workspace_id=OLD.workspace_id;UPDATE workspaces SET "
        "export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND "
        "OLD.expires_at > clock_timestamp(); RETURN NULL; END; $$",
        "CREATE TRIGGER initial_rule_candidate_dependencies_erase AFTER DELETE ON "
        "initial_rule_candidate_dependencies FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_candidate_dependencies_erase_fn()",
        "\n"
        "CREATE TABLE initial_rule_candidate_observations (\n"
        "\tcandidate_job_id VARCHAR(32) NOT NULL, \n"
        "\tobservation_id VARCHAR(32) NOT NULL, \n"
        "\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\taccount_id INTEGER NOT NULL, \n"
        "\tcampaign_id INTEGER NOT NULL, \n"
        "\tPRIMARY KEY (candidate_job_id, observation_id), \n"
        "\tFOREIGN KEY(candidate_job_id, workspace_id, account_id, campaign_id) REFERENCES "
        "initial_rule_candidate_dependencies (candidate_job_id, workspace_id, account_id, "
        "campaign_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(observation_id, workspace_id, account_id, campaign_id) REFERENCES "
        "initial_observations (id, workspace_id, account_id, campaign_id) ON DELETE "
        "CASCADE\n"
        ")\n"
        "\n",
        "CREATE INDEX ix_initial_rule_candidate_observations_expires_at ON "
        "initial_rule_candidate_observations (expires_at)",
        "CREATE FUNCTION initial_rule_candidate_observations_owner_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF NOT (EXISTS(SELECT 1 FROM "
        "initial_rule_candidate_dependencies d JOIN initial_calibration_dependencies c ON "
        "c.calibration_id=d.calibration_id WHERE d.candidate_job_id=NEW.candidate_job_id "
        "AND d.workspace_id=NEW.workspace_id AND d.account_id=NEW.account_id AND "
        "d.campaign_id=NEW.campaign_id AND c.observation_id=NEW.observation_id AND "
        "c.workspace_id=NEW.workspace_id AND c.account_id=NEW.account_id AND "
        "c.campaign_id=NEW.campaign_id AND NEW.expires_at=d.expires_at)) THEN RAISE "
        "EXCEPTION 'owned initial rule lineage required'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER initial_rule_candidate_observations_owner BEFORE INSERT ON "
        "initial_rule_candidate_observations FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_candidate_observations_owner_fn()",
        "CREATE FUNCTION initial_rule_candidate_observations_immutable_fn() RETURNS "
        "trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable initial rule "
        "lineage'; END; $$",
        "CREATE TRIGGER initial_rule_candidate_observations_immutable BEFORE UPDATE ON "
        "initial_rule_candidate_observations FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_candidate_observations_immutable_fn()",
        "CREATE FUNCTION initial_rule_candidate_observations_guard_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id "
        "FOR UPDATE NOWAIT; RETURN OLD; END; $$",
        "CREATE TRIGGER initial_rule_candidate_observations_guard BEFORE DELETE ON "
        "initial_rule_candidate_observations FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_candidate_observations_guard_fn()",
        "CREATE FUNCTION initial_rule_candidate_observations_erase_fn() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN DELETE FROM initial_rule_candidate_dependencies "
        "WHERE candidate_job_id=OLD.candidate_job_id AND "
        "workspace_id=OLD.workspace_id;UPDATE workspaces SET "
        "export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND "
        "OLD.expires_at > clock_timestamp(); RETURN NULL; END; $$",
        "CREATE TRIGGER initial_rule_candidate_observations_erase AFTER DELETE ON "
        "initial_rule_candidate_observations FOR EACH ROW EXECUTE FUNCTION "
        "initial_rule_candidate_observations_erase_fn()",
    ),
    "sqlite": (
        "\n"
        "CREATE TABLE initial_rule_opportunities (\n"
        "\tid VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\tenvironment VARCHAR(16) NOT NULL, \n"
        "\tledger_id VARCHAR(32) NOT NULL, \n"
        "\tnative_account_identity_digest VARCHAR(64) NOT NULL, \n"
        "\tbudget_owner_identity_digest VARCHAR(64) NOT NULL, \n"
        "\tsemantic_key_digest VARCHAR(64) NOT NULL, \n"
        "\tcreated_at DATETIME NOT NULL, \n"
        "\tpending_expires_at DATETIME NOT NULL, \n"
        "\tPRIMARY KEY (id), \n"
        "\tCONSTRAINT uq_initial_rule_opportunity_scope UNIQUE (id, workspace_id), \n"
        "\tCONSTRAINT uq_initial_rule_semantic_key UNIQUE (semantic_key_digest), \n"
        "\tCONSTRAINT uq_initial_rule_native_opportunity UNIQUE (workspace_id, environment, "
        "ledger_id, native_account_identity_digest, budget_owner_identity_digest), \n"
        "\tFOREIGN KEY(ledger_id, workspace_id, environment) REFERENCES "
        "provider_period_ledgers (id, workspace_id, environment) ON DELETE RESTRICT, \n"
        "\tCONSTRAINT ck_initial_rule_env CHECK (environment IN ('contract_test','live')), \n"
        "\tCONSTRAINT ck_initial_rule_pending_expiry CHECK (pending_expires_at > created_at)\n"
        ")\n"
        "\n",
        "CREATE INDEX ix_initial_rule_opportunities_pending_expires_at ON "
        "initial_rule_opportunities (pending_expires_at)",
        "CREATE TRIGGER initial_rule_opportunities_owner BEFORE INSERT ON "
        "initial_rule_opportunities WHEN NOT (NEW.id=substr(NEW.semantic_key_digest,1,32) AND "
        "length(NEW.semantic_key_digest)=64 AND length(NEW.native_account_identity_digest)=64 "
        "AND length(NEW.budget_owner_identity_digest)=64) BEGIN SELECT RAISE(ABORT, 'owned "
        "initial rule lineage required'); END",
        "CREATE TRIGGER initial_rule_opportunities_immutable BEFORE UPDATE ON "
        "initial_rule_opportunities BEGIN SELECT RAISE(ABORT, 'immutable initial rule "
        "lineage'); END",
        "CREATE TRIGGER initial_rule_opportunities_erase AFTER DELETE ON "
        "initial_rule_opportunities BEGIN UPDATE workspaces SET "
        "export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND "
        "julianday(OLD.pending_expires_at) > julianday('now'); END",
        "\n"
        "CREATE TABLE initial_rule_admission_origins (\n"
        "\tadmission_id VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\topportunity_id VARCHAR(32) NOT NULL, \n"
        "\tPRIMARY KEY (admission_id), \n"
        "\tFOREIGN KEY(admission_id, workspace_id) REFERENCES provider_automatic_decisions "
        "(id, workspace_id) ON DELETE RESTRICT, \n"
        "\tFOREIGN KEY(opportunity_id, workspace_id) REFERENCES initial_rule_opportunities "
        "(id, workspace_id) ON DELETE RESTRICT, \n"
        "\tCONSTRAINT uq_initial_rule_consumed_once UNIQUE (opportunity_id)\n"
        ")\n"
        "\n",
        "CREATE TRIGGER initial_rule_admission_origins_owner BEFORE INSERT ON "
        "initial_rule_admission_origins WHEN NOT (EXISTS(SELECT 1 FROM "
        "provider_automatic_decisions a JOIN initial_rule_opportunities o ON "
        "o.id=NEW.opportunity_id JOIN initial_rule_candidate_dependencies d ON "
        "d.opportunity_id=o.id JOIN optimization_candidate_results r ON "
        "r.job_id=d.candidate_job_id WHERE a.id=NEW.admission_id AND "
        "a.workspace_id=NEW.workspace_id AND o.workspace_id=NEW.workspace_id AND "
        "a.ledger_id=o.ledger_id AND a.environment=o.environment AND "
        "a.account_identity_digest=o.native_account_identity_digest AND "
        "r.workspace_id=a.workspace_id AND r.decision_digest=a.candidate_digest AND "
        "r.evidence_digest=a.evidence_digest AND json_extract(r.decision, "
        "'$.scope.budget_owner_key')=a.budget_owner_key AND json_extract(r.decision, "
        "'$.evidence.source_reference')=o.id AND json_extract(r.decision, "
        "'$.evidence.basis.semantic_key_digest')=o.semantic_key_digest AND "
        "json_extract(r.decision, '$.status')='suggested' AND json_extract(r.decision, "
        "'$.schema_version')='inlet.initial-reported-rule-candidate.v1')) BEGIN SELECT "
        "RAISE(ABORT, 'owned initial rule lineage required'); END",
        "CREATE TRIGGER initial_rule_admission_origins_immutable BEFORE UPDATE ON "
        "initial_rule_admission_origins BEGIN SELECT RAISE(ABORT, 'immutable initial rule "
        "lineage'); END",
        "CREATE TRIGGER initial_rule_admission_origins_guard BEFORE DELETE ON "
        "initial_rule_admission_origins BEGIN SELECT RAISE(ABORT, 'protected initial rule "
        "admission'); END",
        "\n"
        "CREATE TABLE initial_rule_candidate_dependencies (\n"
        "\tcandidate_job_id VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\taccount_id INTEGER NOT NULL, \n"
        "\tcampaign_id INTEGER NOT NULL, \n"
        "\topportunity_id VARCHAR(32) NOT NULL, \n"
        "\tpreview_id VARCHAR(32) NOT NULL, \n"
        "\tcalibration_id VARCHAR(32) NOT NULL, \n"
        "\tselected_observation_id VARCHAR(32) NOT NULL, \n"
        "\texpires_at DATETIME NOT NULL, \n"
        "\tPRIMARY KEY (candidate_job_id), \n"
        "\tCONSTRAINT uq_initial_rule_dependency_scope UNIQUE (candidate_job_id, workspace_id, "
        "account_id, campaign_id), \n"
        "\tFOREIGN KEY(candidate_job_id, workspace_id) REFERENCES optimization_candidate_jobs "
        "(id, workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(opportunity_id, workspace_id) REFERENCES initial_rule_opportunities "
        "(id, workspace_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(preview_id, workspace_id, account_id, campaign_id) REFERENCES "
        "initial_plan_previews (id, workspace_id, account_id, campaign_id) ON DELETE "
        "CASCADE, \n"
        "\tFOREIGN KEY(calibration_id, workspace_id, account_id, campaign_id) REFERENCES "
        "initial_calibration_runs (id, workspace_id, account_id, campaign_id) ON DELETE "
        "CASCADE, \n"
        "\tFOREIGN KEY(selected_observation_id, workspace_id, account_id, campaign_id) "
        "REFERENCES initial_observations (id, workspace_id, account_id, campaign_id) ON DELETE "
        "CASCADE\n"
        ")\n"
        "\n",
        "CREATE INDEX ix_initial_rule_candidate_dependencies_expires_at ON "
        "initial_rule_candidate_dependencies (expires_at)",
        "CREATE INDEX ix_initial_rule_candidate_dependencies_opportunity_id ON "
        "initial_rule_candidate_dependencies (opportunity_id)",
        "CREATE TRIGGER initial_rule_candidate_dependencies_owner BEFORE INSERT ON "
        "initial_rule_candidate_dependencies WHEN NOT (EXISTS(SELECT 1 FROM "
        "initial_plan_previews p JOIN initial_calibration_runs c ON c.id=p.calibration_id JOIN "
        "optimization_candidate_jobs j ON j.id=NEW.candidate_job_id JOIN "
        "initial_rule_opportunities o ON o.id=NEW.opportunity_id WHERE p.id=NEW.preview_id AND "
        "p.workspace_id=NEW.workspace_id AND p.account_id=NEW.account_id AND "
        "p.campaign_id=NEW.campaign_id AND p.calibration_id=NEW.calibration_id AND "
        "p.observation_id=NEW.selected_observation_id AND j.workspace_id=p.workspace_id AND "
        "j.actor_id=p.original_actor_id AND j.auth_session_digest=p.original_session_digest "
        "AND j.environment=c.environment AND o.environment=c.environment AND "
        "o.workspace_id=p.workspace_id AND j.attempt_id IS NULL AND "
        "NEW.expires_at<=p.expires_at AND NEW.expires_at<=c.expires_at AND "
        "NEW.expires_at<=o.pending_expires_at)) BEGIN SELECT RAISE(ABORT, 'owned initial rule "
        "lineage required'); END",
        "CREATE TRIGGER initial_rule_candidate_dependencies_immutable BEFORE UPDATE ON "
        "initial_rule_candidate_dependencies BEGIN SELECT RAISE(ABORT, 'immutable initial rule "
        "lineage'); END",
        "CREATE TRIGGER initial_rule_candidate_dependencies_erase AFTER DELETE ON "
        "initial_rule_candidate_dependencies BEGIN DELETE FROM optimization_candidate_jobs "
        "WHERE id=OLD.candidate_job_id AND workspace_id=OLD.workspace_id;UPDATE workspaces SET "
        "export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND "
        "julianday(OLD.expires_at) > julianday('now'); END",
        "\n"
        "CREATE TABLE initial_rule_candidate_observations (\n"
        "\tcandidate_job_id VARCHAR(32) NOT NULL, \n"
        "\tobservation_id VARCHAR(32) NOT NULL, \n"
        "\texpires_at DATETIME NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\taccount_id INTEGER NOT NULL, \n"
        "\tcampaign_id INTEGER NOT NULL, \n"
        "\tPRIMARY KEY (candidate_job_id, observation_id), \n"
        "\tFOREIGN KEY(candidate_job_id, workspace_id, account_id, campaign_id) REFERENCES "
        "initial_rule_candidate_dependencies (candidate_job_id, workspace_id, account_id, "
        "campaign_id) ON DELETE CASCADE, \n"
        "\tFOREIGN KEY(observation_id, workspace_id, account_id, campaign_id) REFERENCES "
        "initial_observations (id, workspace_id, account_id, campaign_id) ON DELETE CASCADE\n"
        ")\n"
        "\n",
        "CREATE INDEX ix_initial_rule_candidate_observations_expires_at ON "
        "initial_rule_candidate_observations (expires_at)",
        "CREATE TRIGGER initial_rule_candidate_observations_owner BEFORE INSERT ON "
        "initial_rule_candidate_observations WHEN NOT (EXISTS(SELECT 1 FROM "
        "initial_rule_candidate_dependencies d JOIN initial_calibration_dependencies c ON "
        "c.calibration_id=d.calibration_id WHERE d.candidate_job_id=NEW.candidate_job_id AND "
        "d.workspace_id=NEW.workspace_id AND d.account_id=NEW.account_id AND "
        "d.campaign_id=NEW.campaign_id AND c.observation_id=NEW.observation_id AND "
        "c.workspace_id=NEW.workspace_id AND c.account_id=NEW.account_id AND "
        "c.campaign_id=NEW.campaign_id AND NEW.expires_at=d.expires_at)) BEGIN SELECT "
        "RAISE(ABORT, 'owned initial rule lineage required'); END",
        "CREATE TRIGGER initial_rule_candidate_observations_immutable BEFORE UPDATE ON "
        "initial_rule_candidate_observations BEGIN SELECT RAISE(ABORT, 'immutable initial rule "
        "lineage'); END",
        "CREATE TRIGGER initial_rule_candidate_observations_erase AFTER DELETE ON "
        "initial_rule_candidate_observations BEGIN DELETE FROM "
        "initial_rule_candidate_dependencies WHERE candidate_job_id=OLD.candidate_job_id AND "
        "workspace_id=OLD.workspace_id;UPDATE workspaces SET "
        "export_privacy_revision=export_privacy_revision+1 WHERE id=OLD.workspace_id AND "
        "julianday(OLD.expires_at) > julianday('now'); END",
    ),
}
