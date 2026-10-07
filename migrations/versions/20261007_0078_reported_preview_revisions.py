# ruff: noqa: E501
"""Immutable reported preview revisions with an exact owned current pointer."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_0078"
down_revision = "20261006_0077"
branch_labels = None
depends_on = None

GROUP = ("workspace_id", "environment", "original_attempt_id", "policy_family", "cohort_digest")
BOUND = (
    "workspace_id",
    "account_id",
    "campaign_id",
    "environment",
    "original_attempt_id",
    "policy_family",
    "cohort_digest",
    "opportunity_digest",
    "revision",
)


def _slot_constraints(up: bool) -> None:
    sqlite = op.get_bind().dialect.name == "sqlite"
    trigger_sql = []
    if sqlite:
        # SQLite reparses every referencing trigger while renaming a batch table.
        # Temporarily remove and restore their exact SQL inside the DDL transaction.
        triggers = list(
            op.get_bind().execute(
                sa.text(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' "
                    "AND instr(sql,'reported_feedback_slots')>0 ORDER BY name"
                )
            )
        )
        for name, statement in triggers:
            trigger_sql.append(statement)
            op.execute('DROP TRIGGER "' + name.replace('"', '""') + '"')
    with op.batch_alter_table("reported_feedback_slots") as batch:
        if up:
            batch.drop_constraint("uq_rf_original_contribution", type_="unique")
            batch.create_unique_constraint("uq_rf_original_revision", [*GROUP, "revision"])
            batch.create_unique_constraint("uq_rf_slot_pointer", ["id", *BOUND])
        else:
            batch.drop_constraint("uq_rf_original_revision", type_="unique")
            batch.drop_constraint("uq_rf_slot_pointer", type_="unique")
            batch.create_unique_constraint("uq_rf_original_contribution", list(GROUP))
    for statement in trigger_sql:
        op.execute(statement)


def upgrade() -> None:
    _slot_constraints(True)
    op.create_table(
        "reported_feedback_current",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("slot_id", sa.String(32), nullable=False),
        *[
            sa.Column(
                f,
                sa.Integer()
                if f in {"workspace_id", "account_id", "campaign_id", "revision"}
                else sa.String(16 if f == "environment" else 64 if f.endswith("digest") else 32),
                nullable=False,
            )
            for f in BOUND
        ],
        sa.UniqueConstraint(*GROUP, name="uq_rf_current_group"),
        sa.ForeignKeyConstraint(
            ["slot_id", *BOUND],
            [f"reported_feedback_slots.{f}" for f in ("id", *BOUND)],
            ondelete="CASCADE",
            name="fk_rf_current_slot",
        ),
        sa.CheckConstraint("revision > 0", name="ck_rf_current_revision"),
    )
    fields = ",".join(BOUND)
    # IDs are preserved in the new pointer's independent namespace. Existing row
    # revision may exceed one and must never be rewritten during migration.
    op.execute(
        f"INSERT INTO reported_feedback_current (id,slot_id,{fields}) SELECT id,id,{fields} FROM reported_feedback_slots"
    )
    for statement in POINTER_SQL[op.get_bind().dialect.name]:
        op.execute(statement)
    if (
        op.get_bind().dialect.name == "sqlite"
        and op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).first()
    ):
        raise RuntimeError("reported feedback revision foreign key validation failed")


def downgrade() -> None:
    grouped = ",".join(GROUP)
    if op.get_bind().scalar(
        sa.text(
            f"SELECT EXISTS(SELECT 1 FROM reported_feedback_slots GROUP BY {grouped} HAVING COUNT(*)>1)"
        )
    ):
        raise RuntimeError("cannot downgrade retained reported feedback revision history")
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM reported_feedback_slots s LEFT JOIN reported_feedback_current c ON c.slot_id=s.id WHERE c.id IS NULL)"
        )
    ):
        raise RuntimeError("cannot downgrade a missing reported feedback current pointer")
    op.drop_table("reported_feedback_current")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION reported_feedback_current_advance_fn()")
        op.execute("DROP FUNCTION reported_feedback_current_guard_fn()")
    _slot_constraints(False)


# Frozen trigger bodies; no application imports.
POINTER_SQL = {
    "sqlite": (
        "CREATE TRIGGER reported_feedback_current_advance BEFORE UPDATE ON reported_feedback_current WHEN NEW.id IS NOT OLD.id OR NEW.workspace_id IS NOT OLD.workspace_id OR NEW.account_id IS NOT OLD.account_id OR NEW.campaign_id IS NOT OLD.campaign_id OR NEW.environment IS NOT OLD.environment OR NEW.original_attempt_id IS NOT OLD.original_attempt_id OR NEW.policy_family IS NOT OLD.policy_family OR NEW.cohort_digest IS NOT OLD.cohort_digest OR NEW.opportunity_digest IS NOT OLD.opportunity_digest OR NEW.revision != OLD.revision+1 OR NEW.slot_id = OLD.slot_id BEGIN SELECT RAISE(ABORT, 'invalid reported feedback pointer advance'); END",
    ),
    "postgresql": (
        "CREATE FUNCTION reported_feedback_current_advance_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.id IS DISTINCT FROM OLD.id OR NEW.workspace_id IS DISTINCT FROM OLD.workspace_id OR NEW.account_id IS DISTINCT FROM OLD.account_id OR NEW.campaign_id IS DISTINCT FROM OLD.campaign_id OR NEW.environment IS DISTINCT FROM OLD.environment OR NEW.original_attempt_id IS DISTINCT FROM OLD.original_attempt_id OR NEW.policy_family IS DISTINCT FROM OLD.policy_family OR NEW.cohort_digest IS DISTINCT FROM OLD.cohort_digest OR NEW.opportunity_digest IS DISTINCT FROM OLD.opportunity_digest OR NEW.revision != OLD.revision+1 OR NEW.slot_id = OLD.slot_id THEN RAISE EXCEPTION 'invalid reported feedback pointer advance'; END IF; PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; RETURN NEW; END; $$",
        "CREATE TRIGGER reported_feedback_current_advance BEFORE UPDATE ON reported_feedback_current FOR EACH ROW EXECUTE FUNCTION reported_feedback_current_advance_fn()",
        "CREATE FUNCTION reported_feedback_current_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; RETURN OLD; END; $$",
        "CREATE TRIGGER reported_feedback_current_guard BEFORE DELETE ON reported_feedback_current FOR EACH ROW EXECUTE FUNCTION reported_feedback_current_guard_fn()",
    ),
}
