# ruff: noqa: E501
"""Durable preview review origin and retractable minimal commitments."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0076"
down_revision = "20261006_0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("provider_execution_reviews") as batch:
        batch.add_column(
            sa.Column(
                "initial_preview_provenance_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("initial_preview_origin_id", sa.String(32), nullable=True))
        batch.create_unique_constraint(
            "uq_initial_review_origin", ["workspace_id", "initial_preview_origin_id"]
        )
        batch.create_check_constraint(
            "ck_initial_review_origin",
            "(NOT initial_preview_provenance_required AND initial_preview_origin_id IS NULL) OR (initial_preview_provenance_required AND initial_preview_origin_id IS NOT NULL AND NOT candidate_provenance_required AND NOT automatic_authority_required)",
        )
    op.create_table(
        "initial_preview_reviews",
        sa.Column("review_id", sa.String(length=32), nullable=False, primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False, primary_key=False),
        sa.Column("preview_id", sa.String(length=32), nullable=True, primary_key=False),
        sa.Column("preview_workspace_id", sa.Integer(), nullable=True, primary_key=False),
        sa.Column("preview_account_id", sa.Integer(), nullable=True, primary_key=False),
        sa.Column("preview_campaign_id", sa.Integer(), nullable=True, primary_key=False),
        sa.Column("actor_id", sa.String(length=32), nullable=False, primary_key=False),
        sa.Column(
            "original_session_digest", sa.String(length=64), nullable=False, primary_key=False
        ),
        sa.Column("environment", sa.String(length=16), nullable=False, primary_key=False),
        sa.Column("preview_digest", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("intent_digest", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("evidence_digest", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("native_state_digest", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("mandate_digest", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("review_digest", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False, primary_key=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.ForeignKeyConstraint(
            ["preview_id", "preview_workspace_id", "preview_account_id", "preview_campaign_id"],
            [
                "initial_plan_previews.id",
                "initial_plan_previews.workspace_id",
                "initial_plan_previews.account_id",
                "initial_plan_previews.campaign_id",
            ],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["customer_users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("environment IN ('contract_test','live')", name="ck_initial_review_env"),
        sa.CheckConstraint(
            "(preview_id IS NULL AND preview_workspace_id IS NULL AND preview_account_id IS NULL AND preview_campaign_id IS NULL) OR (preview_id IS NOT NULL AND preview_workspace_id = workspace_id AND preview_workspace_id IS NOT NULL AND preview_account_id IS NOT NULL AND preview_campaign_id IS NOT NULL)",
            name="ck_initial_review_pointer",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["provider_execution_reviews.id", "provider_execution_reviews.workspace_id"],
            ondelete="RESTRICT",
        ),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION initial_review_origin_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF OLD.initial_preview_origin_id IS NOT NULL AND (NEW.initial_preview_origin_id IS DISTINCT FROM OLD.initial_preview_origin_id OR NOT NEW.initial_preview_provenance_required) THEN RAISE EXCEPTION 'immutable initial preview provenance'; END IF; RETURN NEW; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_review_origin BEFORE UPDATE ON provider_execution_reviews FOR EACH ROW EXECUTE FUNCTION initial_review_origin_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_review_retained_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF OLD.initial_preview_provenance_required THEN RAISE EXCEPTION 'immutable initial preview provenance'; END IF; RETURN OLD; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_review_retained BEFORE DELETE ON provider_execution_reviews FOR EACH ROW EXECUTE FUNCTION initial_review_retained_fn()"
        )
        op.execute(
            "CREATE FUNCTION initial_review_link_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF (NEW.review_id IS DISTINCT FROM OLD.review_id OR NEW.workspace_id IS DISTINCT FROM OLD.workspace_id OR NEW.actor_id IS DISTINCT FROM OLD.actor_id OR NEW.original_session_digest IS DISTINCT FROM OLD.original_session_digest OR NEW.environment IS DISTINCT FROM OLD.environment OR NEW.preview_digest IS DISTINCT FROM OLD.preview_digest OR NEW.intent_digest IS DISTINCT FROM OLD.intent_digest OR NEW.policy_digest IS DISTINCT FROM OLD.policy_digest OR NEW.evidence_digest IS DISTINCT FROM OLD.evidence_digest OR NEW.native_state_digest IS DISTINCT FROM OLD.native_state_digest OR NEW.mandate_digest IS DISTINCT FROM OLD.mandate_digest OR NEW.review_digest IS DISTINCT FROM OLD.review_digest OR NEW.plan_digest IS DISTINCT FROM OLD.plan_digest OR NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.created_at IS DISTINCT FROM OLD.created_at) OR NOT ((NOT (NEW.preview_id IS DISTINCT FROM OLD.preview_id) AND NOT (NEW.preview_workspace_id IS DISTINCT FROM OLD.preview_workspace_id) AND NOT (NEW.preview_account_id IS DISTINCT FROM OLD.preview_account_id) AND NOT (NEW.preview_campaign_id IS DISTINCT FROM OLD.preview_campaign_id)) OR (NEW.preview_id IS NULL AND NEW.preview_workspace_id IS NULL AND NEW.preview_account_id IS NULL AND NEW.preview_campaign_id IS NULL)) THEN RAISE EXCEPTION 'immutable initial preview provenance'; END IF; RETURN NEW; END; $$"
        )
        op.execute(
            "CREATE TRIGGER initial_review_link_immutable BEFORE UPDATE ON initial_preview_reviews FOR EACH ROW EXECUTE FUNCTION initial_review_link_immutable_fn()"
        )
    else:
        op.execute(
            "CREATE TRIGGER initial_review_origin BEFORE UPDATE ON provider_execution_reviews WHEN OLD.initial_preview_origin_id IS NOT NULL AND (NEW.initial_preview_origin_id IS NOT OLD.initial_preview_origin_id OR NOT NEW.initial_preview_provenance_required) BEGIN SELECT RAISE(ABORT, 'immutable initial preview provenance'); END"
        )
        op.execute(
            "CREATE TRIGGER initial_review_retained BEFORE DELETE ON provider_execution_reviews WHEN OLD.initial_preview_provenance_required BEGIN SELECT RAISE(ABORT, 'immutable initial preview provenance'); END"
        )
        op.execute(
            "CREATE TRIGGER initial_review_link_immutable BEFORE UPDATE ON initial_preview_reviews WHEN (NEW.review_id IS NOT OLD.review_id OR NEW.workspace_id IS NOT OLD.workspace_id OR NEW.actor_id IS NOT OLD.actor_id OR NEW.original_session_digest IS NOT OLD.original_session_digest OR NEW.environment IS NOT OLD.environment OR NEW.preview_digest IS NOT OLD.preview_digest OR NEW.intent_digest IS NOT OLD.intent_digest OR NEW.policy_digest IS NOT OLD.policy_digest OR NEW.evidence_digest IS NOT OLD.evidence_digest OR NEW.native_state_digest IS NOT OLD.native_state_digest OR NEW.mandate_digest IS NOT OLD.mandate_digest OR NEW.review_digest IS NOT OLD.review_digest OR NEW.plan_digest IS NOT OLD.plan_digest OR NEW.expires_at IS NOT OLD.expires_at OR NEW.created_at IS NOT OLD.created_at) OR NOT ((NOT (NEW.preview_id IS NOT OLD.preview_id) AND NOT (NEW.preview_workspace_id IS NOT OLD.preview_workspace_id) AND NOT (NEW.preview_account_id IS NOT OLD.preview_account_id) AND NOT (NEW.preview_campaign_id IS NOT OLD.preview_campaign_id)) OR (NEW.preview_id IS NULL AND NEW.preview_workspace_id IS NULL AND NEW.preview_account_id IS NULL AND NEW.preview_campaign_id IS NULL)) BEGIN SELECT RAISE(ABORT, 'immutable initial preview provenance'); END"
        )


def downgrade() -> None:
    db = op.get_bind()
    if db.scalar(
        sa.text(
            "SELECT count(*) FROM provider_execution_reviews WHERE initial_preview_provenance_required OR initial_preview_origin_id IS NOT NULL"
        )
    ) or db.scalar(sa.text("SELECT count(*) FROM initial_preview_reviews")):
        raise RuntimeError("initial preview forward provenance cannot be discarded")
    if db.dialect.name == "postgresql":
        op.execute("DROP TRIGGER initial_review_origin ON provider_execution_reviews")
        op.execute("DROP FUNCTION initial_review_origin_fn()")
    else:
        op.execute("DROP TRIGGER initial_review_origin")
    if db.dialect.name == "postgresql":
        op.execute("DROP TRIGGER initial_review_retained ON provider_execution_reviews")
        op.execute("DROP FUNCTION initial_review_retained_fn()")
    else:
        op.execute("DROP TRIGGER initial_review_retained")
    if db.dialect.name == "postgresql":
        op.execute("DROP TRIGGER initial_review_link_immutable ON initial_preview_reviews")
        op.execute("DROP FUNCTION initial_review_link_immutable_fn()")
    else:
        op.execute("DROP TRIGGER initial_review_link_immutable")
    op.drop_table("initial_preview_reviews")
    with op.batch_alter_table("provider_execution_reviews") as batch:
        batch.drop_constraint("ck_initial_review_origin", type_="check")
        batch.drop_constraint("uq_initial_review_origin", type_="unique")
        batch.drop_column("initial_preview_origin_id")
        batch.drop_column("initial_preview_provenance_required")
