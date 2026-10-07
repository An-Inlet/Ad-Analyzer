"""Owned immutable Start links; only genuine candidate erasure may null references."""

from sqlalchemy import DDL, Table, event

TABLE = "initial_rule_session_starts"


def statements(dialect: str) -> tuple[str, ...]:
    def field(path: str) -> str:
        if dialect == "sqlite":
            return f"json_extract(j.work, '$.{path}')"
        return "j.work #>> '{" + path.replace(".", ",") + "}'"

    equal = "IS" if dialect == "sqlite" else "IS NOT DISTINCT FROM"
    owned = (
        "EXISTS(SELECT 1 FROM session_automation_runs s "
        "JOIN optimization_candidate_jobs j ON j.id=NEW.candidate_job_id "
        "JOIN initial_rule_candidate_dependencies d ON d.candidate_job_id=j.id "
        "WHERE s.id=NEW.session_run_id AND s.workspace_id=NEW.workspace_id "
        "AND j.workspace_id=s.workspace_id AND NEW.candidate_workspace_id=s.workspace_id "
        "AND j.actor_id=s.actor_id AND j.auth_session_digest=s.original_session_digest "
        "AND j.environment=s.environment AND j.input_digest=NEW.input_digest "
        "AND NEW.policy_digest=s.policy_digest AND NEW.expires_at<=s.expires_at "
        "AND NEW.expires_at<=d.expires_at AND NEW.created_at=s.created_at "
        f"AND {field('schema_version')}='inlet.initial-reported-rule-work.v1' "
        f"AND {field('basis.preview_digest')}=NEW.preview_digest "
        f"AND {field('basis.semantic_key_digest')}=NEW.semantic_key_digest "
        f"AND {field('scope.mandate.mandate_id')}=s.mandate_id "
        f"AND CAST({field('scope.mandate.revision')} AS INTEGER)=s.mandate_revision "
        f"AND {field('scope.mandate.consent_id')}=s.consent_id "
        f"AND {field('scope.mandate.policy_digest')}=s.mandate_digest "
        f"AND {field('scope.mandate.ledger_id')}=s.ledger_id)"
    )
    columns = (
        "session_run_id",
        "workspace_id",
        "input_digest",
        "preview_digest",
        "semantic_key_digest",
        "policy_digest",
        "created_at",
        "expires_at",
    )
    null_only = (
        "OLD.candidate_job_id IS NOT NULL AND NEW.candidate_job_id IS NULL "
        "AND NEW.candidate_workspace_id IS NULL AND NOT EXISTS "
        "(SELECT 1 FROM optimization_candidate_jobs WHERE id=OLD.candidate_job_id) AND "
        + " AND ".join(f"NEW.{c} {equal} OLD.{c}" for c in columns)
    )
    if dialect == "sqlite":
        return (
            f"CREATE TRIGGER initial_start_delete BEFORE DELETE ON {TABLE} "
            "BEGIN SELECT RAISE(ABORT,'protected initial Start'); END",
            f"CREATE TRIGGER initial_start_insert BEFORE INSERT ON {TABLE} "
            f"WHEN NOT ({owned}) BEGIN SELECT RAISE(ABORT,'invalid initial Start'); END",
            f"CREATE TRIGGER initial_start_update BEFORE UPDATE ON {TABLE} "
            f"WHEN NOT ({null_only}) BEGIN SELECT RAISE(ABORT,'immutable initial Start'); END",
        )
    return (
        "CREATE FUNCTION initial_start_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ "
        f"BEGIN IF TG_OP='DELETE' OR (TG_OP='INSERT' AND NOT ({owned})) OR "
        f"(TG_OP='UPDATE' AND NOT ({null_only})) THEN "
        "RAISE EXCEPTION 'invalid immutable initial Start'; END IF; RETURN NEW; END; $$",
        f"CREATE TRIGGER initial_start_guard BEFORE INSERT OR UPDATE OR DELETE ON {TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION initial_start_guard_fn()",
    )


def register(table: Table) -> None:
    for dialect in ("sqlite", "postgresql"):
        for sql in statements(dialect):
            event.listen(table, "after_create", DDL(sql).execute_if(dialect=dialect))  # type: ignore[no-untyped-call]
