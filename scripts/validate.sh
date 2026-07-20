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
  if [[ "${DENTICODE_CI_DISPOSABLE_POSTGRES:-}" != "true" && "${DENTICODE_TEST_POSTGRES_URL}" != *"_ci"* && "${DENTICODE_TEST_POSTGRES_URL}" != *"test"* ]]; then
    echo "Refusing migration validation: DENTICODE_TEST_POSTGRES_URL must identify a disposable CI/test database." >&2
    return 1
  fi
  export DATABASE_URL="$DENTICODE_TEST_POSTGRES_URL"
}

focused_validation() { run python -m pytest tests/test_automation_foundation.py; }
postgres_validation() { require_disposable_postgres; run python -m pytest tests/test_phase7_postgres_transactions.py; }
migration_validation() { require_disposable_postgres; run alembic upgrade head; run alembic downgrade base; run alembic upgrade head; }
security_validation() { run python -m pytest tests/test_google_ads_read_only.py tests/test_automation_foundation.py -k "security or approval or controlled or read_only"; }
privacy_validation() { run python -m pytest tests/test_automation_foundation.py; }
readonly_validation() { run python -m pytest tests/test_automation_foundation.py -k "read_only or no_product"; }
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
