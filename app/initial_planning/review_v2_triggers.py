# ruff: noqa: E501
"""Portable owned insert checks and immutable proof rows; no financial admission."""

from sqlalchemy import DDL, Table, event


def statements(dialect: str) -> tuple[str, ...]:
    def value(column: str, path: str) -> str:
        if dialect == "sqlite":
            return f"json_extract({column}, '$.{path}')"
        return f"({column}::jsonb #>> '{{{path.replace('.', ',')}}}')"

    def doc(path: str) -> str:
        return value("NEW.document", path)

    checks = [
        f"{doc('schema_version')} = 'inlet.initial-preview-execution-proof.v1'",
        f"{doc('review_id')} = NEW.review_id",
        f"CAST({doc('workspace_id')} AS BIGINT) = NEW.workspace_id",
        "length(NEW.digest) = 64",
        f"{doc('spending_authority')} = 'none'",
        f"{doc('preview_id')} = l.preview_id",
        f"{doc('preview_digest')} = l.preview_digest",
        f"{doc('qualified_state_digest')} = l.native_state_digest",
        f"{doc('plan_digest')} = l.plan_digest",
        f"{doc('intent_digest')} = l.intent_digest",
        f"{doc('execution_mandate.policy_digest')} = l.mandate_digest",
        f"{doc('execution_mandate.consent_id')} = r.consent_id",
        f"{doc('planning_mandate.policy_digest')} = p.mandate_digest",
        f"{doc('planning_mandate.mandate_id')} = {value('p.intent', 'mandate_id')}",
        f"{doc('planning_mandate.revision')} = {value('p.intent', 'mandate_revision')}",
        f"{doc('planning_mandate.environment')} = l.environment",
        f"{doc('execution_mandate.environment')} = l.environment",
        f"{doc('planning_mandate.ledger_id')} = {doc('execution_mandate.ledger_id')}",
        f"{doc('planning_mandate.mandate_id')} <> {doc('execution_mandate.mandate_id')}",
        f"{doc('planning_mandate.consent_id')} <> {doc('execution_mandate.consent_id')}",
        "l.review_digest = r.digest",
        "l.plan_digest = r.plan_digest",
        "r.initial_preview_provenance_required",
        "r.initial_preview_origin_id = l.preview_id",
        "p.document_digest = l.preview_digest",
        f"{value('p.document', 'schema_version')} = 'inlet.initial-efficiency-preview.v2'",
        f"{value('p.document', 'profile_digest')} = {doc('profile_digest')}",
    ]
    if dialect == "sqlite":
        checks += [
            f"julianday({doc('created_at')}) < julianday({doc('expires_at')})",
            f"julianday({doc('expires_at')}) <= julianday(l.expires_at)",
        ]
    else:
        checks += [
            f"CAST({doc('created_at')} AS timestamptz) < CAST({doc('expires_at')} AS timestamptz)",
            f"CAST({doc('expires_at')} AS timestamptz) <= l.expires_at",
        ]
    valid = (
        "EXISTS (SELECT 1 FROM initial_preview_reviews l JOIN provider_execution_reviews r "
        "ON r.id=l.review_id AND r.workspace_id=l.workspace_id JOIN initial_plan_previews p "
        "ON p.id=l.preview_id AND p.workspace_id=l.workspace_id "
        "WHERE l.review_id=NEW.review_id AND l.workspace_id=NEW.workspace_id AND "
        + " AND ".join(checks)
        + ")"
    )
    if dialect == "sqlite":
        return (
            "CREATE TRIGGER initial_execution_proof_insert BEFORE INSERT ON initial_preview_execution_proofs "
            f"WHEN NOT ({valid}) BEGIN SELECT RAISE(ABORT, 'invalid execution proof binding'); END",
            "CREATE TRIGGER initial_execution_proof_immutable BEFORE UPDATE ON initial_preview_execution_proofs "
            "BEGIN SELECT RAISE(ABORT, 'immutable execution proof'); END",
        )
    return (
        "CREATE FUNCTION initial_execution_proof_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        f"IF TG_OP = 'UPDATE' OR NOT ({valid}) THEN RAISE EXCEPTION 'invalid execution proof binding'; "
        "END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER initial_execution_proof_guard BEFORE INSERT OR UPDATE ON initial_preview_execution_proofs "
        "FOR EACH ROW EXECUTE FUNCTION initial_execution_proof_guard_fn()",
    )


def register(table: Table) -> None:
    for dialect in ("sqlite", "postgresql"):
        for sql in statements(dialect):
            event.listen(table, "after_create", DDL(sql).execute_if(dialect=dialect))  # type: ignore[no-untyped-call]
