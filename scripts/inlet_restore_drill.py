"""Synthetic-only logical restore qualification in one generated disposable schema.

Never accepts an existing backup, source schema, or target schema. No provider calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.customers.access import customer_workspace, customer_workspaces
from app.customers.models import CustomerSession
from app.settings import settings
from fastapi import HTTPException
from scripts.inlet_restore_fixture import (
    seed_financial,
    seed_performance,
    seed_social,
    verify_owned_constraints,
    verify_performance,
    verify_performance_constraints,
    verify_populated,
)
from scripts.inlet_restore_initial_fixture import (
    seed_initial,
    verify_initial,
    verify_initial_constraints,
)
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import MetaData, Table, create_engine, inspect, make_url, select, text
from sqlalchemy.engine import URL, Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class DrillError(RuntimeError):
    """Fixed diagnostic only; never include a DSN, raw row, archive, or command output."""


def target() -> URL:
    url = make_url(validate_disposable_url())
    if url.host not in {"localhost", "127.0.0.1", "::1"} or url.query:
        raise DrillError("restore drill requires a loopback disposable target without URL options")
    return url


class PostgresTools:
    def __init__(self, url: URL, container: str | None) -> None:
        if container is not None and not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", container
        ):
            raise DrillError("invalid local PostgreSQL container name")
        self.container = container
        self.env = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
            "PGHOST": "127.0.0.1" if container else str(url.host),
            "PGPORT": "5432" if container else str(url.port or 5432),
            "PGUSER": url.username or "postgres",
            "PGDATABASE": str(url.database),
            "PGPASSFILE": "/dev/null",
            "PGSERVICEFILE": "/dev/null",
            "PGCONNECT_TIMEOUT": "5",
            "PGAPPNAME": "inlet-synthetic-restore-drill",
        }
        if url.password:
            self.env["PGPASSWORD"] = url.password
        required = ["docker"] if container else ["pg_dump", "pg_restore", "psql"]
        if not all(shutil.which(tool) for tool in required):
            raise DrillError("required local PostgreSQL tools are unavailable")

    def run(self, tool: str, args: list[str], payload: bytes | None = None) -> bytes:
        if tool not in {"pg_dump", "pg_restore", "psql"}:
            raise DrillError("unsupported PostgreSQL drill operation")
        command_args = [tool, *args]
        if self.container:
            # Docker reads these values from the child environment, never argv.
            command_args = ["docker", "--context", "default", "exec", "-i"]
            for key in self.env:
                if key.startswith("PG"):
                    command_args.extend(["--env", key])
            command_args.extend([self.container, tool, *args])
        try:
            result = subprocess.run(
                command_args,
                input=payload,
                capture_output=True,
                env=self.env,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise DrillError("PostgreSQL drill operation unavailable") from None
        if result.returncode:
            raise DrillError("PostgreSQL drill operation failed")
        return result.stdout

    def prove_server(self, db: Connection) -> None:
        query = (
            "SELECT system_identifier::text || '-' || "
            "(SELECT oid::text FROM pg_database WHERE datname=current_database()) "
            "FROM pg_control_system()"
        )
        expected = str(db.scalar(text(query)))
        actual = (
            self.run("psql", ["-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", query])
            .decode()
            .strip()
        )
        if not expected or actual != expected:
            raise DrillError("PostgreSQL container or tool target identity mismatch")


def insert(db: Connection, table_name: str, **values: Any) -> None:
    table = Table(table_name, MetaData(), autoload_with=db)
    db.execute(table.insert().values(**values))


def seed(engine: Engine) -> None:
    now = datetime(2026, 10, 6, tzinfo=UTC)
    stamps = {"created_at": now, "updated_at": now}
    with engine.begin() as db:
        for tenant in (1, 2):
            wid, user = 900 + tenant, str(tenant) * 32
            insert(
                db,
                "workspaces",
                id=wid,
                slug=f"restore-fixture-{tenant}",
                name="Synthetic",
                client_name="Synthetic",
                status="active",
                is_default=False,
                **stamps,
            )
            insert(
                db,
                "customer_users",
                id=user,
                issuer="restore-fixture",
                subject=user,
                email=f"fixture-{tenant}@example.invalid",
                status="active",
            )
            insert(
                db,
                "customer_memberships",
                user_id=user,
                workspace_id=wid,
                role="owner",
                status="active",
            )
            insert(
                db,
                "customer_sessions",
                digest=str(tenant) * 64,
                user_id=user,
                csrf_digest="c" * 64,
                created_at=1,
                authenticated_at=1,
                expires_at=2**40,
                revoked_at=2 if tenant == 2 else None,
            )
            insert(
                db,
                "workspace_integrations",
                id=wid,
                workspace_id=wid,
                integration_key="klaviyo",
                provider="klaviyo",
                display_name="Synthetic metadata only",
                status="active",
                configuration={},
                **stamps,
            )
            insert(
                db,
                "customer_source_connections",
                id=f"restore-source-{tenant}",
                workspace_id=wid,
                integration_id=wid,
                provider="klaviyo",
                external_id=f"fixture-account-{tenant}",
                encrypted_grant=None,
                status="disconnected",
                generation=2,
                window_start=now.date(),
                window_end=now.date(),
                staged={},
            )
            insert(db, "customer_goals", id=f"restore-goal-{tenant}", workspace_id=wid, revision=1)
            insert(
                db,
                "customer_goal_revisions",
                goal_id=f"restore-goal-{tenant}",
                revision=1,
                workspace_id=wid,
                definition={"milestone": "Synthetic restore fixture", "amount": 100 * tenant},
                editor_id=user,
                created_at=now,
            )

    seed_financial(engine)
    seed_social(engine)
    seed_performance(engine)
    seed_initial(engine)


def normalized_text_casts(expression: str) -> str:
    """Normalize only equivalent unbounded varchar/text literal-array casts.

    pg_dump/restore may distribute an array's text cast to its literal elements.
    Keep Boolean operators, grouping, predicates and all other casts untouched.
    """
    literal = r"'(?:[^']|'')*'"
    expression = re.sub(r"\((" + literal + r")::character varying\)::text", r"\1::text", expression)
    expression = re.sub(r"(" + literal + r")::character varying::text", r"\1::text", expression)
    expression = re.sub(r"(" + literal + r")::character varying", r"\1::text", expression)
    items = literal + r"::text(?:, " + literal + r"::text)*"
    expression = re.sub(r"\(ARRAY\[(" + items + r")\]\)::text\[\]", r"ARRAY[\1]", expression)
    return re.sub(r"ARRAY\[(" + items + r")\]::text\[\]", r"ARRAY[\1]", expression)


def fingerprint(db: Connection, schema: str) -> tuple[str, int, int]:
    inspector = inspect(db)
    evidence: dict[str, Any] = {}
    row_count = 0
    for name in sorted(inspector.get_table_names()):
        table = Table(name, MetaData(), autoload_with=db)
        rows = [dict(row) for row in db.execute(select(table)).mappings()]
        row_count += len(rows)
        evidence[name] = {
            "rows": sorted(json.dumps(row, sort_keys=True, default=str) for row in rows),
            "columns": inspector.get_columns(name),
            "pk": inspector.get_pk_constraint(name),
            "fk": sorted(
                inspector.get_foreign_keys(name), key=lambda value: str(value.get("name"))
            ),
            "unique": sorted(
                inspector.get_unique_constraints(name), key=lambda value: str(value.get("name"))
            ),
            "checks": sorted(
                inspector.get_check_constraints(name), key=lambda value: str(value.get("name"))
            ),
            "indexes": sorted(
                inspector.get_indexes(name), key=lambda value: str(value.get("name"))
            ),
        }
    for name in inspector.get_table_names():
        for check in evidence[name]["checks"]:
            check["sqltext"] = normalized_text_casts(check["sqltext"])
        for index in evidence[name]["indexes"]:
            options = index.get("dialect_options", {})
            if "postgresql_where" in options:
                options["postgresql_where"] = normalized_text_casts(options["postgresql_where"])
    evidence["sequences"] = {
        name: list(db.execute(text(f'SELECT last_value,is_called FROM "{schema}"."{name}"')).one())
        for name in sorted(inspector.get_sequence_names())
    }
    evidence["privileges"] = [
        list(row)
        for row in db.execute(
            text(
                "SELECT table_name,grantor,grantee,privilege_type,is_grantable "
                "FROM information_schema.table_privileges "
                "WHERE table_schema=:schema "
                "ORDER BY table_name,grantor,grantee,privilege_type,is_grantable"
            ),
            {"schema": schema},
        )
    ]
    evidence["schema_acl"] = [
        list(row)
        for row in db.execute(
            text(
                "SELECT nspowner::regrole::text,a.grantor::regrole::text,a.grantee::text,"
                "a.privilege_type,a.is_grantable FROM pg_namespace "
                "CROSS JOIN LATERAL aclexplode(COALESCE(nspacl,acldefault('n',nspowner))) a "
                "WHERE nspname=:schema ORDER BY 1,2,3,4,5"
            ),
            {"schema": schema},
        )
    ]
    return (
        hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode()).hexdigest(),
        len(inspector.get_table_names()),
        row_count,
    )


def verify_isolation(engine: Engine) -> None:
    with Session(engine) as db:
        for tenant in (1, 2):
            wid, user = 900 + tenant, str(tenant) * 32
            if [row.id for row, _ in customer_workspaces(db, user)] != [wid]:
                raise DrillError("restored customer membership isolation failed")
            customer_workspace(db, user, wid)
            try:
                customer_workspace(db, user, 903 - tenant)
            except HTTPException as error:
                if error.status_code != 404:
                    raise DrillError("restored cross-workspace access check failed") from None
            else:
                raise DrillError("restored cross-workspace access was allowed")
            session = db.get(CustomerSession, str(tenant) * 64)
            if (
                session is None
                or session.user_id != user
                or session.revoked_at != (2 if tenant == 2 else None)
            ):
                raise DrillError("restored session revocation metadata failed")
    # Real PostgreSQL composite FK rejects a connection assigned to another tenant.
    with engine.connect() as db:
        transaction = db.begin()
        try:
            db.execute(
                text(
                    "UPDATE customer_source_connections SET integration_id=902 "
                    "WHERE id='restore-source-1'"
                )
            )
        except IntegrityError:
            transaction.rollback()
        else:
            transaction.rollback()
            raise DrillError("restored provider ownership constraint failed")


def run_drill(container: str | None = None) -> dict[str, Any]:
    if not __debug__:
        raise DrillError("restore drill requires enabled verification assertions")
    url = target()
    tools = PostgresTools(url, container)
    schema = "inlet_restore_" + uuid4().hex
    admin = create_engine(url)
    engine = create_engine(url.update_query_dict({"options": f"-csearch_path={schema}"}))
    previous = settings.database_url
    created = False
    try:
        with admin.begin() as db:
            tools.prove_server(db)
            db.execute(text(f'CREATE SCHEMA "{schema}"'))
            db.execute(text(f'REVOKE ALL ON SCHEMA "{schema}" FROM PUBLIC'))
            created = True
        settings.database_url = engine.url.render_as_string(hide_password=False)
        config = Config("alembic.ini")
        command.upgrade(config, "head")
        seed(engine)
        verify_isolation(engine)
        verify_populated(engine)
        verify_owned_constraints(engine)
        verify_performance(engine)
        verify_performance_constraints(engine)
        verify_initial(engine)
        verify_initial_constraints(engine)
        with engine.connect() as db:
            before, table_count, row_count = fingerprint(db, schema)
        archive = tools.run("pg_dump", ["--format=custom", "--no-owner", f"--schema={schema}"])
        if not archive.startswith(b"PGDMP") or len(archive) > 20_000_000:
            raise DrillError("synthetic backup archive invalid")
        engine.dispose()
        with admin.begin() as db:
            tools.prove_server(db)
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        # Only the archive produced above is consumed; no external archive argument exists.
        tools.run(
            "pg_restore",
            ["--exit-on-error", "--no-owner", f"--dbname={url.database}"],
            archive,
        )
        with engine.connect() as db:
            after, restored_tables, restored_rows = fingerprint(db, schema)
            if (after, restored_tables, restored_rows) != (before, table_count, row_count):
                raise DrillError("restored schema privileges constraints or data mismatch")
            if (
                db.scalar(text("SELECT version_num FROM alembic_version"))
                != ScriptDirectory.from_config(config).get_current_head()
            ):
                raise DrillError("restored migration revision mismatch")
        command.upgrade(config, "head")
        verify_isolation(engine)
        verify_populated(engine)
        verify_owned_constraints(engine)
        verify_performance(engine)
        verify_performance_constraints(engine)
        verify_initial(engine)
        verify_initial_constraints(engine)
        with engine.connect() as db:
            if fingerprint(db, schema) != (before, table_count, row_count):
                raise DrillError("restored behavioral checks changed durable evidence")
        return {
            "status": "passed",
            "scope": "synthetic_disposable_postgresql",
            "workspaces": 2,
            "tables_verified": table_count,
            "rows_verified": row_count,
            "schema_data_privileges_sha256": before,
            "archive_bytes": len(archive),
            "isolation_verified": True,
            "populated_financial_lineage_verified": True,
            "social_approval_verified": True,
            "campaign_performance_verified": True,
            "initial_planning_graph_verified": True,
            "initial_session_digest_excluded": True,
            "unknown_attempt_replay_denied": True,
            "media_objects_restored": False,
            "live_restore_qualified": False,
        }
    finally:
        settings.database_url = previous
        engine.dispose()
        if created:
            with admin.begin() as db:
                db.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--postgres-container", help="Explicit local test PostgreSQL container; identity checked"
    )
    args = parser.parse_args()
    try:
        result = run_drill(args.postgres_container)
    except Exception:
        print("Synthetic restore drill failed; no database details are emitted.", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
