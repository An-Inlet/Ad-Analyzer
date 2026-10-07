# ruff: noqa: E501
"""Protected exact initial-rule Start binding with erasable candidate reference."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_0085"
down_revision = "20261007_0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM initial_rule_session_starts)")):
        raise RuntimeError("cannot discard retained initial Start commitments")
    op.drop_table("initial_rule_session_starts")
    if connection.dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS initial_start_guard_fn()")


# Frozen DDL does not depend on evolving application models.
SQL = {
    "postgresql": (
        "\n"
        "CREATE TABLE initial_rule_session_starts (\n"
        "\tsession_run_id VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\tcandidate_job_id VARCHAR(32), \n"
        "\tcandidate_workspace_id INTEGER, \n"
        "\tinput_digest VARCHAR(64) NOT NULL, \n"
        "\tpreview_digest VARCHAR(64) NOT NULL, \n"
        "\tsemantic_key_digest VARCHAR(64) NOT NULL, \n"
        "\tpolicy_digest VARCHAR(64) NOT NULL, \n"
        "\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n"
        "\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n"
        "\tPRIMARY KEY (session_run_id), \n"
        "\tFOREIGN KEY(session_run_id, workspace_id) REFERENCES session_automation_runs "
        "(id, workspace_id) ON DELETE RESTRICT, \n"
        "\tFOREIGN KEY(candidate_job_id, candidate_workspace_id) REFERENCES "
        "optimization_candidate_jobs (id, workspace_id) ON DELETE SET NULL, \n"
        "\tCONSTRAINT ck_initial_start_optional_scope CHECK ((candidate_job_id IS NULL "
        "AND candidate_workspace_id IS NULL) OR (candidate_job_id IS NOT NULL AND "
        "candidate_workspace_id = workspace_id AND candidate_workspace_id IS NOT "
        "NULL)), \n"
        "\tCONSTRAINT ck_initial_start_lifetime CHECK (expires_at > created_at)\n"
        ")\n"
        "\n",
        "CREATE FUNCTION initial_start_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN IF TG_OP='DELETE' OR (TG_OP='INSERT' AND NOT (EXISTS(SELECT 1 FROM "
        "session_automation_runs s JOIN optimization_candidate_jobs j ON "
        "j.id=NEW.candidate_job_id JOIN initial_rule_candidate_dependencies d ON "
        "d.candidate_job_id=j.id WHERE s.id=NEW.session_run_id AND "
        "s.workspace_id=NEW.workspace_id AND j.workspace_id=s.workspace_id AND "
        "NEW.candidate_workspace_id=s.workspace_id AND j.actor_id=s.actor_id AND "
        "j.auth_session_digest=s.original_session_digest AND j.environment=s.environment "
        "AND j.input_digest=NEW.input_digest AND NEW.policy_digest=s.policy_digest AND "
        "NEW.expires_at<=s.expires_at AND NEW.expires_at<=d.expires_at AND "
        "NEW.created_at=s.created_at AND j.work #>> "
        "'{schema_version}'='inlet.initial-reported-rule-work.v1' AND j.work #>> "
        "'{basis,preview_digest}'=NEW.preview_digest AND j.work #>> "
        "'{basis,semantic_key_digest}'=NEW.semantic_key_digest AND j.work #>> "
        "'{scope,mandate,mandate_id}'=s.mandate_id AND CAST(j.work #>> "
        "'{scope,mandate,revision}' AS INTEGER)=s.mandate_revision AND j.work #>> "
        "'{scope,mandate,consent_id}'=s.consent_id AND j.work #>> "
        "'{scope,mandate,policy_digest}'=s.mandate_digest AND j.work #>> "
        "'{scope,mandate,ledger_id}'=s.ledger_id))) OR (TG_OP='UPDATE' AND NOT "
        "(OLD.candidate_job_id IS NOT NULL AND NEW.candidate_job_id IS NULL AND "
        "NEW.candidate_workspace_id IS NULL AND NOT EXISTS (SELECT 1 FROM "
        "optimization_candidate_jobs WHERE id=OLD.candidate_job_id) AND "
        "NEW.session_run_id IS NOT DISTINCT FROM OLD.session_run_id AND NEW.workspace_id "
        "IS NOT DISTINCT FROM OLD.workspace_id AND NEW.input_digest IS NOT DISTINCT FROM "
        "OLD.input_digest AND NEW.preview_digest IS NOT DISTINCT FROM OLD.preview_digest "
        "AND NEW.semantic_key_digest IS NOT DISTINCT FROM OLD.semantic_key_digest AND "
        "NEW.policy_digest IS NOT DISTINCT FROM OLD.policy_digest AND NEW.created_at IS "
        "NOT DISTINCT FROM OLD.created_at AND NEW.expires_at IS NOT DISTINCT FROM "
        "OLD.expires_at)) THEN RAISE EXCEPTION 'invalid immutable initial Start'; END "
        "IF; RETURN NEW; END; $$",
        "CREATE TRIGGER initial_start_guard BEFORE INSERT OR UPDATE OR DELETE ON "
        "initial_rule_session_starts FOR EACH ROW EXECUTE FUNCTION "
        "initial_start_guard_fn()",
    ),
    "sqlite": (
        "\n"
        "CREATE TABLE initial_rule_session_starts (\n"
        "\tsession_run_id VARCHAR(32) NOT NULL, \n"
        "\tworkspace_id INTEGER NOT NULL, \n"
        "\tcandidate_job_id VARCHAR(32), \n"
        "\tcandidate_workspace_id INTEGER, \n"
        "\tinput_digest VARCHAR(64) NOT NULL, \n"
        "\tpreview_digest VARCHAR(64) NOT NULL, \n"
        "\tsemantic_key_digest VARCHAR(64) NOT NULL, \n"
        "\tpolicy_digest VARCHAR(64) NOT NULL, \n"
        "\tcreated_at DATETIME NOT NULL, \n"
        "\texpires_at DATETIME NOT NULL, \n"
        "\tPRIMARY KEY (session_run_id), \n"
        "\tFOREIGN KEY(session_run_id, workspace_id) REFERENCES session_automation_runs (id, "
        "workspace_id) ON DELETE RESTRICT, \n"
        "\tFOREIGN KEY(candidate_job_id, candidate_workspace_id) REFERENCES "
        "optimization_candidate_jobs (id, workspace_id) ON DELETE SET NULL, \n"
        "\tCONSTRAINT ck_initial_start_optional_scope CHECK ((candidate_job_id IS NULL AND "
        "candidate_workspace_id IS NULL) OR (candidate_job_id IS NOT NULL AND "
        "candidate_workspace_id = workspace_id AND candidate_workspace_id IS NOT NULL)), \n"
        "\tCONSTRAINT ck_initial_start_lifetime CHECK (expires_at > created_at)\n"
        ")\n"
        "\n",
        "CREATE TRIGGER initial_start_delete BEFORE DELETE ON initial_rule_session_starts "
        "BEGIN SELECT RAISE(ABORT,'protected initial Start'); END",
        "CREATE TRIGGER initial_start_insert BEFORE INSERT ON initial_rule_session_starts "
        "WHEN NOT (EXISTS(SELECT 1 FROM session_automation_runs s JOIN "
        "optimization_candidate_jobs j ON j.id=NEW.candidate_job_id JOIN "
        "initial_rule_candidate_dependencies d ON d.candidate_job_id=j.id WHERE "
        "s.id=NEW.session_run_id AND s.workspace_id=NEW.workspace_id AND "
        "j.workspace_id=s.workspace_id AND NEW.candidate_workspace_id=s.workspace_id AND "
        "j.actor_id=s.actor_id AND j.auth_session_digest=s.original_session_digest AND "
        "j.environment=s.environment AND j.input_digest=NEW.input_digest AND "
        "NEW.policy_digest=s.policy_digest AND NEW.expires_at<=s.expires_at AND "
        "NEW.expires_at<=d.expires_at AND NEW.created_at=s.created_at AND "
        "json_extract(j.work, '$.schema_version')='inlet.initial-reported-rule-work.v1' AND "
        "json_extract(j.work, '$.basis.preview_digest')=NEW.preview_digest AND "
        "json_extract(j.work, '$.basis.semantic_key_digest')=NEW.semantic_key_digest AND "
        "json_extract(j.work, '$.scope.mandate.mandate_id')=s.mandate_id AND "
        "CAST(json_extract(j.work, '$.scope.mandate.revision') AS "
        "INTEGER)=s.mandate_revision AND json_extract(j.work, "
        "'$.scope.mandate.consent_id')=s.consent_id AND json_extract(j.work, "
        "'$.scope.mandate.policy_digest')=s.mandate_digest AND json_extract(j.work, "
        "'$.scope.mandate.ledger_id')=s.ledger_id)) BEGIN SELECT RAISE(ABORT,'invalid "
        "initial Start'); END",
        "CREATE TRIGGER initial_start_update BEFORE UPDATE ON initial_rule_session_starts "
        "WHEN NOT (OLD.candidate_job_id IS NOT NULL AND NEW.candidate_job_id IS NULL AND "
        "NEW.candidate_workspace_id IS NULL AND NOT EXISTS (SELECT 1 FROM "
        "optimization_candidate_jobs WHERE id=OLD.candidate_job_id) AND NEW.session_run_id "
        "IS OLD.session_run_id AND NEW.workspace_id IS OLD.workspace_id AND NEW.input_digest "
        "IS OLD.input_digest AND NEW.preview_digest IS OLD.preview_digest AND "
        "NEW.semantic_key_digest IS OLD.semantic_key_digest AND NEW.policy_digest IS "
        "OLD.policy_digest AND NEW.created_at IS OLD.created_at AND NEW.expires_at IS "
        "OLD.expires_at) BEGIN SELECT RAISE(ABORT,'immutable initial Start'); END",
    ),
}
