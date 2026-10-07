"""Portable scope/immutability and immediate source-erasure guards for read staging."""

from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Connection

from app.database.session import Base

IMMUTABLE = (
    "id",
    "workspace_id",
    "store_id",
    "native_connection_id",
    "integration_id",
    "goal_id",
    "goal_revision",
    "actor_id",
    "session_digest",
    "authenticated_at",
    "identity_digest",
    "environment",
    "request",
    "request_digest",
    "profile",
    "profile_digest",
    "created_at",
    "deadline_at",
)


def statements(dialect: str) -> tuple[str, ...]:
    def field(column: str, path: str) -> str:
        if dialect == "sqlite":
            return f"json_extract({column}, '$.{path}')"
        return f"({column}::jsonb #>> '{{{path.replace('.', ',')}}}')"

    same = " AND ".join(
        f"CAST(NEW.{name} AS TEXT) IS NOT DISTINCT FROM CAST(OLD.{name} AS TEXT)"
        if dialect == "postgresql"
        else f"NEW.{name} IS OLD.{name}"
        for name in IMMUTABLE
    )
    bound = (
        "EXISTS(SELECT 1 FROM shopify_connections n JOIN commerce_stores s "
        "ON s.id=NEW.store_id AND s.workspace_id=NEW.workspace_id "
        "JOIN customer_sessions a ON a.digest=NEW.session_digest "
        "JOIN customer_goal_revisions g ON g.goal_id=NEW.goal_id AND g.revision=NEW.goal_revision "
        "WHERE n.id=NEW.native_connection_id AND n.workspace_id=NEW.workspace_id "
        "AND n.commerce_store_id=s.id AND n.workspace_integration_id=NEW.integration_id "
        "AND s.connection_id=NEW.integration_id AND a.user_id=NEW.actor_id "
        "AND a.authenticated_at=NEW.authenticated_at AND g.workspace_id=NEW.workspace_id) "
        f"AND {field('NEW.request', 'acquisition_id')}=NEW.id "
        f"AND {field('NEW.request', 'scope.store_id')}=NEW.store_id "
        f"AND {field('NEW.request', 'scope.goal_id')}=NEW.goal_id "
        f"AND CAST({field('NEW.request', 'scope.workspace_id')} AS BIGINT)=NEW.workspace_id "
        f"AND CAST({field('NEW.request', 'scope.goal_revision')} AS BIGINT)=NEW.goal_revision "
        f"AND CAST({field('NEW.request', 'connection_id')} AS BIGINT)=NEW.integration_id"
    )
    if dialect == "sqlite":
        bound += " AND (SELECT foreign_keys FROM pragma_foreign_keys)=1"
    checkpoint = (
        "EXISTS(SELECT 1 FROM commerce_acquisition_jobs j WHERE j.id=NEW.job_id "
        "AND j.workspace_id=NEW.workspace_id AND j.state IN ('pending','running') "
        "AND j.step_sequence=NEW.sequence "
        f"AND {field('NEW.state_document', 'request_digest')}=j.request_digest "
        f"AND {field('NEW.state_document', 'profile_digest')}=j.profile_digest) "
        f"AND {field('NEW.state_document', 'phase')}=NEW.phase "
        f"AND CAST({field('NEW.state_document', 'sequence')} AS BIGINT)=NEW.sequence "
        "AND length(CAST(NEW.state_document AS TEXT))<=131072"
    )
    sql: list[str] = []

    def trigger(name: str, table: str, operation: str, when: str, action: str) -> None:
        if dialect == "sqlite":
            sql.append(
                f"CREATE TRIGGER IF NOT EXISTS {name} {operation} ON {table} "
                f"WHEN {when} BEGIN {action}; END"
            )
        else:
            sql.append(
                f"CREATE OR REPLACE FUNCTION {name}_fn() RETURNS trigger LANGUAGE plpgsql "
                f"AS $$ BEGIN IF {when} THEN {action}; END IF; RETURN NEW; END; $$"
            )
            sql.append(f"DROP TRIGGER IF EXISTS {name} ON {table}")
            sql.append(
                f"CREATE TRIGGER {name} {operation} ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {name}_fn()"
            )

    failure = (
        "SELECT RAISE(ABORT, 'invalid acquisition binding')"
        if dialect == "sqlite"
        else "RAISE EXCEPTION 'invalid acquisition binding'"
    )
    trigger(
        "acq_job_insert",
        "commerce_acquisition_jobs",
        "BEFORE INSERT",
        f"NOT COALESCE(({bound}), FALSE)",
        failure,
    )
    trigger(
        "acq_job_immutable",
        "commerce_acquisition_jobs",
        "BEFORE UPDATE",
        f"NOT ({same}) OR (OLD.started_at IS NOT NULL AND "
        "(NEW.started_at IS NULL OR NEW.started_at<>OLD.started_at))",
        failure,
    )
    for op in ("INSERT", "UPDATE"):
        trigger(
            "acq_checkpoint_" + op.lower(),
            "commerce_acquisition_checkpoints",
            "BEFORE " + op,
            f"NOT COALESCE(({checkpoint}), FALSE)",
            failure,
        )
    # Updates rather than deletes cover revocation, rebind and source/privacy epochs.
    invalidations = (
        ("user", "customer_users", "NEW.status <> 'active'", "actor_id=NEW.id"),
        (
            "membership",
            "customer_memberships",
            "NEW.status <> 'active' OR NEW.role <> 'owner'",
            "actor_id=NEW.user_id AND workspace_id=NEW.workspace_id",
        ),
        (
            "integration",
            "workspace_integrations",
            "NEW.status <> 'active'",
            "integration_id=NEW.id AND workspace_id=NEW.workspace_id",
        ),
        (
            "store",
            "commerce_stores",
            "NEW.status <> 'active' OR NEW.revision<>OLD.revision",
            "store_id=NEW.id AND workspace_id=NEW.workspace_id",
        ),
        (
            "workspace",
            "workspaces",
            "NEW.status <> 'active' OR NEW.export_privacy_revision <> OLD.export_privacy_revision",
            "workspace_id=NEW.id",
        ),
        (
            "session",
            "customer_sessions",
            "NEW.revoked_at IS NOT NULL OR "
            "NEW.authenticated_at<>OLD.authenticated_at OR NEW.user_id<>OLD.user_id",
            "session_digest=NEW.digest",
        ),
        (
            "source",
            "shopify_connections",
            "NEW.status <> 'connected' OR "
            "NEW.connected_at<>OLD.connected_at OR "
            "NEW.encrypted_credentials<>OLD.encrypted_credentials",
            "native_connection_id=NEW.id AND workspace_id=NEW.workspace_id",
        ),
        (
            "privacy",
            "commerce_evidence_states",
            "NEW.generation<>OLD.generation OR NEW.privacy_epoch<>OLD.privacy_epoch",
            "store_id=NEW.store_id AND workspace_id=NEW.workspace_id",
        ),
        (
            "goal",
            "customer_goals",
            "NEW.revision<>OLD.revision",
            "goal_id=NEW.id AND workspace_id=NEW.workspace_id",
        ),
    )
    for name, table, condition, selector in invalidations:
        trigger(
            "acq_erase_" + name,
            table,
            "AFTER UPDATE",
            condition,
            "DELETE FROM commerce_acquisition_jobs WHERE " + selector,
        )
    return tuple(sql)


@event.listens_for(Base.metadata, "after_create")
def install(metadata: Any, connection: Connection, **kwargs: Any) -> None:
    if "commerce_acquisition_jobs" not in {t.name for t in kwargs.get("tables", ())}:
        return
    for sql in statements(connection.dialect.name):
        connection.exec_driver_sql(sql)
