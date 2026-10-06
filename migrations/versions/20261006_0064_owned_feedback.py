"""Erasable multi-evidence v3 assessments and bounded feedback slots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0064"
down_revision: str | Sequence[str] | None = "20261006_0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outcome_assessments_v3",
        sa.Column("id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("store_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("environment", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("attempt_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("receipt_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("receipt_sequence", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("generation", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("privacy_epoch", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("input_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("document_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("document", sa.JSON(), primary_key=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["store_id", "workspace_id"],
            ["commerce_stores.id", "commerce_stores.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["attempt_id", "workspace_id"],
            ["provider_execution_attempts.id", "provider_execution_attempts.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id", "workspace_id"],
            ["provider_execution_receipts.id", "provider_execution_receipts.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "environment IN ('contract_test','live') AND generation > 0 "
            "AND privacy_epoch > 0 AND receipt_sequence > 0",
            name="ck_v3_fences",
        ),
        sa.UniqueConstraint(
            "id", "workspace_id", "environment", "attempt_id", name="uq_v3_feedback_binding"
        ),
        sa.UniqueConstraint("workspace_id", "input_digest", name="uq_v3_input"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_v3_owner"),
    )
    op.create_table(
        "outcome_assessment_v3_evidence",
        sa.Column("assessment_id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("ordinal", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("publication_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("manifest_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("completion_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id", "workspace_id"],
            ["outcome_assessments_v3.id", "outcome_assessments_v3.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["publication_id", "workspace_id"],
            [
                "commerce_measurement_publications.id",
                "commerce_measurement_publications.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("ordinal >= 0 AND ordinal <= 32", name="ck_v3_dependency_bound"),
        sa.UniqueConstraint("assessment_id", "publication_id", name="uq_v3_dependency_publication"),
    )
    op.create_index(
        "ix_outcome_assessment_v3_evidence_publication_id",
        "outcome_assessment_v3_evidence",
        ["publication_id"],
    )
    op.create_table(
        "outcome_feedback_records",
        sa.Column("id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("environment", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("attempt_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("assessment_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("assessment_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("policy_family", sa.String(length=80), primary_key=False, nullable=False),
        sa.Column("policy_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("scope_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("document_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("document", sa.JSON(), primary_key=False, nullable=False),
        sa.Column("state", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assessment_id", "workspace_id", "environment", "attempt_id"],
            [
                "outcome_assessments_v3.id",
                "outcome_assessments_v3.workspace_id",
                "outcome_assessments_v3.environment",
                "outcome_assessments_v3.attempt_id",
            ],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("state IN ('eligible','superseded')", name="ck_feedback_state"),
        sa.UniqueConstraint(
            "workspace_id",
            "environment",
            "assessment_digest",
            "policy_digest",
            "scope_digest",
            name="uq_feedback_input",
        ),
        sa.UniqueConstraint("id", "workspace_id", name="uq_feedback_owner"),
        sa.UniqueConstraint(
            "id",
            "workspace_id",
            "environment",
            "attempt_id",
            "policy_family",
            "scope_digest",
            name="uq_feedback_slot_binding",
        ),
    )
    op.create_table(
        "outcome_contribution_slots",
        sa.Column("id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("environment", sa.String(length=16), primary_key=False, nullable=False),
        sa.Column("attempt_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("policy_family", sa.String(length=80), primary_key=False, nullable=False),
        sa.Column("scope_digest", sa.String(length=64), primary_key=False, nullable=False),
        sa.Column("feedback_id", sa.String(length=32), primary_key=False, nullable=False),
        sa.Column("revision", sa.Integer(), primary_key=False, nullable=False),
        sa.ForeignKeyConstraint(
            [
                "feedback_id",
                "workspace_id",
                "environment",
                "attempt_id",
                "policy_family",
                "scope_digest",
            ],
            [
                "outcome_feedback_records.id",
                "outcome_feedback_records.workspace_id",
                "outcome_feedback_records.environment",
                "outcome_feedback_records.attempt_id",
                "outcome_feedback_records.policy_family",
                "outcome_feedback_records.scope_digest",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.CheckConstraint("revision > 0", name="ck_contribution_revision"),
        sa.UniqueConstraint(
            "workspace_id",
            "environment",
            "attempt_id",
            "policy_family",
            "scope_digest",
            name="uq_contribution_slot",
        ),
    )
    op.create_index(
        "ix_v3_workspace_source", "outcome_assessments_v3", ["workspace_id", "store_id"]
    )
    op.create_index(
        "ix_v3_workspace_attempt", "outcome_assessments_v3", ["workspace_id", "attempt_id"]
    )
    _install_triggers()


def _install_triggers() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table in (
            "outcome_assessment_v3_evidence",
            "outcome_assessments_v3",
            "outcome_feedback_records",
            "outcome_contribution_slots",
        ):
            guard = f"inlet_guard_{table}"
            body = (
                "IF TG_OP='INSERT' THEN PERFORM id FROM workspaces WHERE id=NEW.workspace_id "
                "FOR UPDATE NOWAIT; ELSIF TG_OP='UPDATE' THEN PERFORM id FROM workspaces "
                "WHERE id IN (OLD.workspace_id, NEW.workspace_id) ORDER BY id FOR UPDATE NOWAIT; "
                "ELSE PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; "
                "END IF; IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;"
            )
            op.execute(
                f"CREATE FUNCTION {guard}_fn() RETURNS trigger LANGUAGE plpgsql "
                f"AS $$ BEGIN {body} END; $$"
            )
            op.execute(
                f"CREATE TRIGGER {guard} BEFORE DELETE OR UPDATE"
                + (" OR INSERT" if table == "outcome_contribution_slots" else "")
                + f" ON {table} FOR EACH ROW EXECUTE FUNCTION {guard}_fn()"
            )
    for table, body in (
        (
            "outcome_assessment_v3_evidence",
            "DELETE FROM outcome_assessments_v3 WHERE id=OLD.assessment_id "
            "AND workspace_id=OLD.workspace_id;",
        ),
        *(
            (
                table,
                "DELETE FROM optimization_candidate_jobs WHERE workspace_id=OLD.workspace_id; "
                "UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 "
                "WHERE id=OLD.workspace_id;",
            )
            for table in (
                "outcome_assessments_v3",
                "outcome_feedback_records",
                "outcome_contribution_slots",
            )
        ),
    ):
        for action in (
            ("DELETE", "UPDATE", "INSERT")
            if table == "outcome_contribution_slots"
            else ("DELETE", "UPDATE")
        ):
            name = f"inlet_{table}_{action.lower()}"
            action_body = body.replace("OLD.", "NEW.") if action == "INSERT" else body
            if action == "UPDATE":
                action_body += body.replace("OLD.", "NEW.")
            if dialect == "sqlite":
                op.execute(
                    f"CREATE TRIGGER {name} AFTER {action} ON {table} "
                    f"FOR EACH ROW BEGIN {action_body} END"
                )
            elif dialect == "postgresql":
                op.execute(
                    f"CREATE FUNCTION {name}_fn() RETURNS trigger LANGUAGE plpgsql "
                    f"AS $$ BEGIN {action_body} RETURN NULL; END; $$"
                )
                op.execute(
                    f"CREATE TRIGGER {name} AFTER {action} ON {table} "
                    f"FOR EACH ROW EXECUTE FUNCTION {name}_fn()"
                )
            else:
                raise RuntimeError("unsupported feedback trigger database")


def downgrade() -> None:
    op.drop_table("outcome_contribution_slots")
    op.drop_table("outcome_feedback_records")
    op.drop_table("outcome_assessment_v3_evidence")
    op.drop_table("outcome_assessments_v3")
    if op.get_bind().dialect.name == "postgresql":
        for table in (
            "outcome_assessment_v3_evidence",
            "outcome_assessments_v3",
            "outcome_feedback_records",
            "outcome_contribution_slots",
        ):
            op.execute(f"DROP FUNCTION inlet_guard_{table}_fn()")
            for action in (
                ("delete", "update", "insert")
                if table == "outcome_contribution_slots"
                else ("delete", "update")
            ):
                op.execute(f"DROP FUNCTION inlet_{table}_{action}_fn()")
