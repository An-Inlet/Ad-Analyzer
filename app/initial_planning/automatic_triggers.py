"""Immutable owned initial-rule graph; raw retraction cannot leave detached results."""

from sqlalchemy import DDL, Table, event

TABLES = (
    "initial_rule_opportunities",
    "initial_rule_admission_origins",
    "initial_rule_candidate_dependencies",
    "initial_rule_candidate_observations",
)


def statements(table: str, dialect: str) -> tuple[str, ...]:
    if table not in TABLES:
        raise ValueError("unknown initial rule table")
    if table == TABLES[0]:
        owned = (
            "NEW.id=substr(NEW.semantic_key_digest,1,32) "
            "AND length(NEW.semantic_key_digest)=64 "
            "AND length(NEW.native_account_identity_digest)=64 "
            "AND length(NEW.budget_owner_identity_digest)=64"
        )
        deletion = ""
    elif table == TABLES[1]:

        def field(path: str) -> str:
            if dialect == "sqlite":
                return "json_extract(r.decision, '$." + path + "')"
            return "r.decision #>> '{" + path.replace(".", ",") + "}'"

        owned = (
            "EXISTS(SELECT 1 FROM provider_automatic_decisions a "
            "JOIN initial_rule_opportunities o ON o.id=NEW.opportunity_id "
            "JOIN initial_rule_candidate_dependencies d ON d.opportunity_id=o.id "
            "JOIN optimization_candidate_results r ON r.job_id=d.candidate_job_id "
            "WHERE a.id=NEW.admission_id AND a.workspace_id=NEW.workspace_id "
            "AND o.workspace_id=NEW.workspace_id AND a.ledger_id=o.ledger_id "
            "AND a.environment=o.environment "
            "AND a.account_identity_digest=o.native_account_identity_digest "
            "AND r.workspace_id=a.workspace_id AND r.decision_digest=a.candidate_digest "
            "AND r.evidence_digest=a.evidence_digest "
            f"AND {field('scope.budget_owner_key')}=a.budget_owner_key "
            f"AND {field('evidence.source_reference')}=o.id "
            f"AND {field('evidence.basis.semantic_key_digest')}=o.semantic_key_digest "
            f"AND {field('status')}='suggested' "
            f"AND {field('schema_version')}='inlet.initial-reported-rule-candidate.v1')"
        )
        deletion = ""
    elif table == TABLES[2]:
        owned = (
            "EXISTS(SELECT 1 FROM initial_plan_previews p "
            "JOIN initial_calibration_runs c ON c.id=p.calibration_id "
            "JOIN optimization_candidate_jobs j ON j.id=NEW.candidate_job_id "
            "JOIN initial_rule_opportunities o ON o.id=NEW.opportunity_id "
            "WHERE p.id=NEW.preview_id AND p.workspace_id=NEW.workspace_id "
            "AND p.account_id=NEW.account_id AND p.campaign_id=NEW.campaign_id "
            "AND p.calibration_id=NEW.calibration_id "
            "AND p.observation_id=NEW.selected_observation_id "
            "AND j.workspace_id=p.workspace_id AND j.actor_id=p.original_actor_id "
            "AND j.auth_session_digest=p.original_session_digest "
            "AND j.environment=c.environment AND o.environment=c.environment "
            "AND o.workspace_id=p.workspace_id AND j.attempt_id IS NULL "
            "AND NEW.expires_at<=p.expires_at AND NEW.expires_at<=c.expires_at "
            "AND NEW.expires_at<=o.pending_expires_at)"
        )
        deletion = (
            "DELETE FROM optimization_candidate_jobs WHERE id=OLD.candidate_job_id "
            "AND workspace_id=OLD.workspace_id;"
        )
    else:
        owned = (
            "EXISTS(SELECT 1 FROM initial_rule_candidate_dependencies d "
            "JOIN initial_calibration_dependencies c ON c.calibration_id=d.calibration_id "
            "WHERE d.candidate_job_id=NEW.candidate_job_id "
            "AND d.workspace_id=NEW.workspace_id AND d.account_id=NEW.account_id "
            "AND d.campaign_id=NEW.campaign_id AND c.observation_id=NEW.observation_id "
            "AND c.workspace_id=NEW.workspace_id AND c.account_id=NEW.account_id "
            "AND c.campaign_id=NEW.campaign_id AND NEW.expires_at=d.expires_at)"
        )
        deletion = (
            "DELETE FROM initial_rule_candidate_dependencies WHERE "
            "candidate_job_id=OLD.candidate_job_id AND workspace_id=OLD.workspace_id;"
        )
    # Graph changes revoke any previously prepared export. They never call semantic
    # privacy erasure recursively or touch financial obligations.
    deadline = "pending_expires_at" if table == TABLES[0] else "expires_at"
    live = (
        f"julianday(OLD.{deadline}) > julianday('now')"
        if dialect == "sqlite"
        else f"OLD.{deadline} > clock_timestamp()"
    )
    if table == TABLES[1]:
        live = "TRUE"  # protected delete guard always rejects first
    deletion += (
        "UPDATE workspaces SET export_privacy_revision=export_privacy_revision+1 "
        f"WHERE id=OLD.workspace_id AND {live};"
    )
    protected = table == TABLES[1]
    if dialect == "sqlite":
        result = [
            f"CREATE TRIGGER {table}_owner BEFORE INSERT ON {table} WHEN NOT ({owned}) "
            "BEGIN SELECT RAISE(ABORT, 'owned initial rule lineage required'); END",
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE ON {table} BEGIN "
            "SELECT RAISE(ABORT, 'immutable initial rule lineage'); END",
        ]
        if protected:
            result.append(
                f"CREATE TRIGGER {table}_guard BEFORE DELETE ON {table} BEGIN "
                "SELECT RAISE(ABORT, 'protected initial rule admission'); END"
            )
        else:
            result.append(
                f"CREATE TRIGGER {table}_erase AFTER DELETE ON {table} BEGIN {deletion} END"
            )
        return tuple(result)
    guard = (
        "RAISE EXCEPTION 'protected initial rule admission';"
        if protected
        else "PERFORM id FROM workspaces WHERE id=OLD.workspace_id FOR UPDATE NOWAIT; RETURN OLD;"
    )
    result = [
        f"CREATE FUNCTION {table}_owner_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        f"IF NOT ({owned}) THEN RAISE EXCEPTION 'owned initial rule lineage required'; "
        "END IF; RETURN NEW; END; $$",
        f"CREATE TRIGGER {table}_owner BEFORE INSERT ON {table} FOR EACH ROW "
        f"EXECUTE FUNCTION {table}_owner_fn()",
        f"CREATE FUNCTION {table}_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION 'immutable initial rule lineage'; END; $$",
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE ON {table} FOR EACH ROW "
        f"EXECUTE FUNCTION {table}_immutable_fn()",
        f"CREATE FUNCTION {table}_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ "
        f"BEGIN {guard} END; $$",
        f"CREATE TRIGGER {table}_guard BEFORE DELETE ON {table} FOR EACH ROW "
        f"EXECUTE FUNCTION {table}_guard_fn()",
    ]
    if not protected:
        result.extend(
            (
                f"CREATE FUNCTION {table}_erase_fn() RETURNS trigger LANGUAGE plpgsql AS $$ "
                f"BEGIN {deletion} RETURN NULL; END; $$",
                f"CREATE TRIGGER {table}_erase AFTER DELETE ON {table} FOR EACH ROW "
                f"EXECUTE FUNCTION {table}_erase_fn()",
            )
        )
    return tuple(result)


def register(table: Table) -> None:
    for dialect in ("sqlite", "postgresql"):
        for statement in statements(table.name, dialect):
            event.listen(table, "after_create", DDL(statement).execute_if(dialect=dialect))  # type: ignore[no-untyped-call]
