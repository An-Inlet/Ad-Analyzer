"""Reset a guarded disposable PostgreSQL schema for migration validation."""

from __future__ import annotations

import os
import sys
from typing import NoReturn
from urllib.parse import unquote, urlparse

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

SAFE_SCHEME_NAMES = {"postgresql", "postgresql+psycopg"}
FORBIDDEN_DATABASE_NAME_PARTS = ("prod", "production", "stage", "staging")


def fail(message: str) -> NoReturn:
    print(f"Refusing disposable PostgreSQL reset: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_disposable_url() -> str:
    if os.environ.get("DENTICODE_CI_DISPOSABLE_POSTGRES") != "true":
        fail("DENTICODE_CI_DISPOSABLE_POSTGRES must exactly equal true.")

    url = os.environ.get("DENTICODE_TEST_POSTGRES_URL")
    if not url:
        fail("DENTICODE_TEST_POSTGRES_URL is not configured.")

    try:
        parsed = urlparse(url)
    except ValueError:
        fail("malformed DENTICODE_TEST_POSTGRES_URL.")

    if parsed.scheme not in SAFE_SCHEME_NAMES:
        fail("DENTICODE_TEST_POSTGRES_URL must use a PostgreSQL scheme.")
    if not parsed.path or parsed.path == "/":
        fail("PostgreSQL database name is empty.")

    database_name = unquote(parsed.path.rsplit("/", 1)[-1]).lower()
    if not database_name:
        fail("PostgreSQL database name is empty.")
    if any(forbidden in database_name for forbidden in FORBIDDEN_DATABASE_NAME_PARTS):
        fail("staging/production database names are never disposable.")
    if not (
        database_name.endswith("_ci")
        or database_name.endswith("_test")
        or "_ci_" in database_name
        or "_test_" in database_name
    ):
        fail("database name must use a controlled _ci or _test naming convention.")

    try:
        make_url(url)
    except Exception:
        fail("malformed DENTICODE_TEST_POSTGRES_URL.")

    return url


def reset_public_schema(url: str) -> None:
    try:
        engine = create_engine(url, future=True)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
            connection.exec_driver_sql("GRANT ALL ON SCHEMA public TO CURRENT_USER")
            connection.exec_driver_sql("GRANT USAGE ON SCHEMA public TO PUBLIC")
    except SQLAlchemyError as exc:
        print(
            f"Disposable PostgreSQL schema reset failed: {exc.__class__.__name__}.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def main() -> int:
    url = validate_disposable_url()
    reset_public_schema(url)
    print("Disposable PostgreSQL schema reset completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
