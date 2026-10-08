# ruff: noqa: E501
"""Independent erasable planning confirmations, never execution consent."""

import sqlalchemy as sa
from alembic import op

revision = "20261008_0086"
down_revision = "20261007_0085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in SQL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM initial_planning_consents)")):
        raise RuntimeError("cannot discard retained planning confirmations")
    op.drop_table("initial_planning_consents")
    if connection.dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS ipc_guard_fn()")


# Frozen DDL, independent of application model imports.
SQL = {
    "postgresql": (
        "\nCREATE TABLE initial_planning_consents (\n\tmandate_id VARCHAR(32) NOT NULL, \n\tmandate_revision INTEGER NOT NULL, \n\tworkspace_id INTEGER NOT NULL, \n\tpolicy_digest VARCHAR(64) NOT NULL, \n\tpreparation_digest VARCHAR(64) NOT NULL, \n\tactor VARCHAR(32) NOT NULL, \n\tconfirmed_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tdigest VARCHAR(64) NOT NULL, \n\tPRIMARY KEY (mandate_id, mandate_revision), \n\tCONSTRAINT fk_planning_consent_preparation FOREIGN KEY(mandate_id, mandate_revision) REFERENCES initial_budget_mandate_preparations (mandate_id, mandate_revision) ON DELETE RESTRICT, \n\tCONSTRAINT ck_planning_consent_revision CHECK (mandate_revision > 0)\n)\n\n",
        "CREATE FUNCTION ipc_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP != 'INSERT' THEN RAISE EXCEPTION 'immutable planning confirmation'; END IF; IF NOT EXISTS (SELECT 1 FROM initial_budget_mandate_preparations p JOIN provider_execution_revisions r ON r.mandate_id=p.mandate_id AND r.revision=p.mandate_revision AND r.workspace_id=p.workspace_id WHERE p.mandate_id=NEW.mandate_id AND p.mandate_revision=NEW.mandate_revision AND p.workspace_id=NEW.workspace_id AND p.policy_digest=NEW.policy_digest AND p.digest=NEW.preparation_digest AND r.digest=NEW.policy_digest) THEN RAISE EXCEPTION 'planning consent preparation mismatch'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER ipc_guard BEFORE INSERT OR UPDATE ON initial_planning_consents FOR EACH ROW EXECUTE FUNCTION ipc_guard_fn()",
    ),
    "sqlite": (
        "\nCREATE TABLE initial_planning_consents (\n\tmandate_id VARCHAR(32) NOT NULL, \n\tmandate_revision INTEGER NOT NULL, \n\tworkspace_id INTEGER NOT NULL, \n\tpolicy_digest VARCHAR(64) NOT NULL, \n\tpreparation_digest VARCHAR(64) NOT NULL, \n\tactor VARCHAR(32) NOT NULL, \n\tconfirmed_at DATETIME NOT NULL, \n\tdigest VARCHAR(64) NOT NULL, \n\tPRIMARY KEY (mandate_id, mandate_revision), \n\tCONSTRAINT fk_planning_consent_preparation FOREIGN KEY(mandate_id, mandate_revision) REFERENCES initial_budget_mandate_preparations (mandate_id, mandate_revision) ON DELETE RESTRICT, \n\tCONSTRAINT ck_planning_consent_revision CHECK (mandate_revision > 0)\n)\n\n",
        "CREATE TRIGGER ipc_insert BEFORE INSERT ON initial_planning_consents WHEN NOT EXISTS (SELECT 1 FROM initial_budget_mandate_preparations p JOIN provider_execution_revisions r ON r.mandate_id=p.mandate_id AND r.revision=p.mandate_revision AND r.workspace_id=p.workspace_id WHERE p.mandate_id=NEW.mandate_id AND p.mandate_revision=NEW.mandate_revision AND p.workspace_id=NEW.workspace_id AND p.policy_digest=NEW.policy_digest AND p.digest=NEW.preparation_digest AND r.digest=NEW.policy_digest) BEGIN SELECT RAISE(ABORT,'planning consent preparation mismatch'); END",
        "CREATE TRIGGER ipc_update BEFORE UPDATE ON initial_planning_consents BEGIN SELECT RAISE(ABORT,'immutable planning confirmation'); END",
    ),
}
