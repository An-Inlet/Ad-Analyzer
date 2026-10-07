# ruff: noqa: E501
"""Owned immutable hash-only v2 preview execution proof."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_0081"
down_revision = "20261007_0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_initial_review_owned",
        "initial_preview_reviews",
        ["review_id", "workspace_id"],
        unique=True,
    )
    op.create_table(
        "initial_preview_execution_proofs",
        sa.Column("review_id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), primary_key=True),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["initial_preview_reviews.review_id", "initial_preview_reviews.workspace_id"],
            ondelete="CASCADE",
            name="fk_initial_execution_proof_link",
        ),
    )
    for sql in SQL[op.get_bind().dialect.name]:
        op.execute(sql)


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM initial_preview_execution_proofs)")
    ):
        raise RuntimeError("cannot discard retained initial execution proof")
    op.drop_table("initial_preview_execution_proofs")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION initial_execution_proof_guard_fn()")
    op.drop_index("uq_initial_review_owned", table_name="initial_preview_reviews")


# Frozen SQL, no imports of evolving application validation.
SQL = {
    "sqlite": (
        "CREATE TRIGGER initial_execution_proof_insert BEFORE INSERT ON initial_preview_execution_proofs WHEN NOT (EXISTS (SELECT 1 FROM initial_preview_reviews l JOIN provider_execution_reviews r ON r.id=l.review_id AND r.workspace_id=l.workspace_id JOIN initial_plan_previews p ON p.id=l.preview_id AND p.workspace_id=l.workspace_id WHERE l.review_id=NEW.review_id AND l.workspace_id=NEW.workspace_id AND json_extract(NEW.document, '$.schema_version') = 'inlet.initial-preview-execution-proof.v1' AND json_extract(NEW.document, '$.review_id') = NEW.review_id AND CAST(json_extract(NEW.document, '$.workspace_id') AS BIGINT) = NEW.workspace_id AND length(NEW.digest) = 64 AND json_extract(NEW.document, '$.spending_authority') = 'none' AND json_extract(NEW.document, '$.preview_id') = l.preview_id AND json_extract(NEW.document, '$.preview_digest') = l.preview_digest AND json_extract(NEW.document, '$.qualified_state_digest') = l.native_state_digest AND json_extract(NEW.document, '$.plan_digest') = l.plan_digest AND json_extract(NEW.document, '$.intent_digest') = l.intent_digest AND json_extract(NEW.document, '$.execution_mandate.policy_digest') = l.mandate_digest AND json_extract(NEW.document, '$.execution_mandate.consent_id') = r.consent_id AND json_extract(NEW.document, '$.planning_mandate.policy_digest') = p.mandate_digest AND json_extract(NEW.document, '$.planning_mandate.mandate_id') = json_extract(p.intent, '$.mandate_id') AND json_extract(NEW.document, '$.planning_mandate.revision') = json_extract(p.intent, '$.mandate_revision') AND json_extract(NEW.document, '$.planning_mandate.environment') = l.environment AND json_extract(NEW.document, '$.execution_mandate.environment') = l.environment AND json_extract(NEW.document, '$.planning_mandate.ledger_id') = json_extract(NEW.document, '$.execution_mandate.ledger_id') AND json_extract(NEW.document, '$.planning_mandate.mandate_id') <> json_extract(NEW.document, '$.execution_mandate.mandate_id') AND json_extract(NEW.document, '$.planning_mandate.consent_id') <> json_extract(NEW.document, '$.execution_mandate.consent_id') AND l.review_digest = r.digest AND l.plan_digest = r.plan_digest AND r.initial_preview_provenance_required AND r.initial_preview_origin_id = l.preview_id AND p.document_digest = l.preview_digest AND json_extract(p.document, '$.schema_version') = 'inlet.initial-efficiency-preview.v2' AND json_extract(p.document, '$.profile_digest') = json_extract(NEW.document, '$.profile_digest') AND julianday(json_extract(NEW.document, '$.created_at')) < julianday(json_extract(NEW.document, '$.expires_at')) AND julianday(json_extract(NEW.document, '$.expires_at')) <= julianday(l.expires_at))) BEGIN SELECT RAISE(ABORT, 'invalid execution proof binding'); END",
        "CREATE TRIGGER initial_execution_proof_immutable BEFORE UPDATE ON initial_preview_execution_proofs BEGIN SELECT RAISE(ABORT, 'immutable execution proof'); END",
    ),
    "postgresql": (
        "CREATE FUNCTION initial_execution_proof_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'UPDATE' OR NOT (EXISTS (SELECT 1 FROM initial_preview_reviews l JOIN provider_execution_reviews r ON r.id=l.review_id AND r.workspace_id=l.workspace_id JOIN initial_plan_previews p ON p.id=l.preview_id AND p.workspace_id=l.workspace_id WHERE l.review_id=NEW.review_id AND l.workspace_id=NEW.workspace_id AND (NEW.document::jsonb #>> '{schema_version}') = 'inlet.initial-preview-execution-proof.v1' AND (NEW.document::jsonb #>> '{review_id}') = NEW.review_id AND CAST((NEW.document::jsonb #>> '{workspace_id}') AS BIGINT) = NEW.workspace_id AND length(NEW.digest) = 64 AND (NEW.document::jsonb #>> '{spending_authority}') = 'none' AND (NEW.document::jsonb #>> '{preview_id}') = l.preview_id AND (NEW.document::jsonb #>> '{preview_digest}') = l.preview_digest AND (NEW.document::jsonb #>> '{qualified_state_digest}') = l.native_state_digest AND (NEW.document::jsonb #>> '{plan_digest}') = l.plan_digest AND (NEW.document::jsonb #>> '{intent_digest}') = l.intent_digest AND (NEW.document::jsonb #>> '{execution_mandate,policy_digest}') = l.mandate_digest AND (NEW.document::jsonb #>> '{execution_mandate,consent_id}') = r.consent_id AND (NEW.document::jsonb #>> '{planning_mandate,policy_digest}') = p.mandate_digest AND (NEW.document::jsonb #>> '{planning_mandate,mandate_id}') = (p.intent::jsonb #>> '{mandate_id}') AND (NEW.document::jsonb #>> '{planning_mandate,revision}') = (p.intent::jsonb #>> '{mandate_revision}') AND (NEW.document::jsonb #>> '{planning_mandate,environment}') = l.environment AND (NEW.document::jsonb #>> '{execution_mandate,environment}') = l.environment AND (NEW.document::jsonb #>> '{planning_mandate,ledger_id}') = (NEW.document::jsonb #>> '{execution_mandate,ledger_id}') AND (NEW.document::jsonb #>> '{planning_mandate,mandate_id}') <> (NEW.document::jsonb #>> '{execution_mandate,mandate_id}') AND (NEW.document::jsonb #>> '{planning_mandate,consent_id}') <> (NEW.document::jsonb #>> '{execution_mandate,consent_id}') AND l.review_digest = r.digest AND l.plan_digest = r.plan_digest AND r.initial_preview_provenance_required AND r.initial_preview_origin_id = l.preview_id AND p.document_digest = l.preview_digest AND (p.document::jsonb #>> '{schema_version}') = 'inlet.initial-efficiency-preview.v2' AND (p.document::jsonb #>> '{profile_digest}') = (NEW.document::jsonb #>> '{profile_digest}') AND CAST((NEW.document::jsonb #>> '{created_at}') AS timestamptz) < CAST((NEW.document::jsonb #>> '{expires_at}') AS timestamptz) AND CAST((NEW.document::jsonb #>> '{expires_at}') AS timestamptz) <= l.expires_at)) THEN RAISE EXCEPTION 'invalid execution proof binding'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER initial_execution_proof_guard BEFORE INSERT OR UPDATE ON initial_preview_execution_proofs FOR EACH ROW EXECUTE FUNCTION initial_execution_proof_guard_fn()",
    ),
}
