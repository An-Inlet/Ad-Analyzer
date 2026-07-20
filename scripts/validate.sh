#!/usr/bin/env bash
set -euo pipefail

scope="${1:-Full}"
case "$scope" in
  Full|Focused|PostgreSQL|Migrations|Security|Privacy|ReadOnly|ControlledWrites|Release) ;;
  *) echo "Usage: $0 [Full|Focused|PostgreSQL|Migrations|Security|Privacy|ReadOnly|ControlledWrites|Release]" >&2; exit 2 ;;
esac

run() { echo "+ $*"; "$@"; }

require_disposable_postgres() {
  if [[ -z "${DENTICODE_TEST_POSTGRES_URL:-}" ]]; then
    echo "DENTICODE_TEST_POSTGRES_URL is not configured; PostgreSQL integration testing cannot run." >&2
    return 1
  fi
  if [[ "${DENTICODE_CI_DISPOSABLE_POSTGRES:-}" != "true" ]]; then
    echo "Refusing migration validation: DENTICODE_CI_DISPOSABLE_POSTGRES must exactly equal true." >&2
    return 1
  fi
  python - <<'PY_VALIDATE_POSTGRES'
import os
import sys
from urllib.parse import unquote, urlparse

url = os.environ.get("DENTICODE_TEST_POSTGRES_URL", "")
try:
    parsed = urlparse(url)
except ValueError as exc:
    print(f"Refusing migration validation: malformed DENTICODE_TEST_POSTGRES_URL ({exc}).", file=sys.stderr)
    sys.exit(1)

if parsed.scheme not in {"postgresql", "postgresql+psycopg"} or not parsed.path or parsed.path == "/":
    print("Refusing migration validation: DENTICODE_TEST_POSTGRES_URL must be a PostgreSQL URL with a database name.", file=sys.stderr)
    sys.exit(1)

database_name = unquote(parsed.path.rsplit("/", 1)[-1]).lower()
if not database_name:
    print("Refusing migration validation: PostgreSQL database name is empty.", file=sys.stderr)
    sys.exit(1)
if any(forbidden in database_name for forbidden in ("prod", "production", "stage", "staging")):
    print("Refusing migration validation: staging/production database names are never disposable.", file=sys.stderr)
    sys.exit(1)
if not (database_name.endswith("_ci") or database_name.endswith("_test") or "_ci_" in database_name or "_test_" in database_name):
    print("Refusing migration validation: database name must use a controlled _ci or _test naming convention.", file=sys.stderr)
    sys.exit(1)
PY_VALIDATE_POSTGRES
  export DATABASE_URL="$DENTICODE_TEST_POSTGRES_URL"
}

focused_validation() { run python -m pytest tests/test_automation_foundation.py tests/test_api_v1_read_only.py -k "automation_foundation or scoping or account_scoped or no_writes"; }
postgres_validation() { require_disposable_postgres; run python -m pytest tests/test_phase7_postgres_transactions.py; }
migration_validation() { require_disposable_postgres; run alembic upgrade head; run alembic downgrade base; run alembic upgrade head; }
security_validation() { run python -m pytest tests/test_google_ads_read_only.py tests/test_token_files.py tests/test_generate_google_ads_refresh_token.py tests/test_api_v1_read_only.py tests/test_automation_foundation.py -k "read_only or token or secret or credential or sanitized or error_messages or controlled or approval"; }
privacy_validation() { run python -m pytest tests/test_api_v1_read_only.py tests/test_automation_foundation.py -k "sanitized or secret or credential or token or error_messages or sensitive or search_term"; }
readonly_validation() { run python -m pytest tests/test_google_ads_read_only.py tests/test_api_v1_read_only.py tests/test_automation_foundation.py -k "read_only or no_writes or no_product or pre_write"; }
controlled_writes_validation() { echo "ControlledWrites gates are intentionally not implemented before Phase 11 approved policy and human authorization." >&2; return 1; }
release_validation() { echo "Release gates are intentionally not implemented before Phase 12 production release approval." >&2; return 1; }

case "$scope" in
  Full)
    if [[ -n "${DENTICODE_TEST_POSTGRES_URL:-}" ]]; then export DATABASE_URL="$DENTICODE_TEST_POSTGRES_URL"; else echo "DENTICODE_TEST_POSTGRES_URL is not configured; PostgreSQL integration testing cannot run locally."; fi
    run alembic upgrade head
    run python -m pytest
    run ruff check .
    run mypy
    run git diff --check "${DENTICODE_DIFF_BASE:-HEAD}"
    if [[ -n "${DENTICODE_TEST_POSTGRES_URL:-}" ]]; then postgres_validation; migration_validation; fi
    readonly_validation; security_validation; privacy_validation; focused_validation
    ;;
  Focused) focused_validation ;;
  PostgreSQL) postgres_validation ;;
  Migrations) migration_validation ;;
  Security) security_validation ;;
  Privacy) privacy_validation ;;
  ReadOnly) readonly_validation ;;
  ControlledWrites) controlled_writes_validation ;;
  Release) release_validation ;;
esac
