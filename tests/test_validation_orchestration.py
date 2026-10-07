"""Exercise real shell orchestration without recursively executing its test payloads.

Only leaf tools are replaced. Database reset/migration behavior remains covered by
actual PostgreSQL tests in test_automation_foundation and by required Full gates.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_automation_foundation import (
    ROOT,
    bash_validate_command,
    minimal_subprocess_env,
    powershell_validate_command,
)

GATES = [
    ["python", "scripts/reset_disposable_postgres.py"],
    ["alembic", "upgrade", "head"],
    ["python", "-m", "pytest"],
    ["ruff", "check", "."],
    ["mypy"],
    ["git", "diff", "--check", "fixture-base"],
    ["python", "-m", "pytest", "tests/test_phase7_postgres_transactions.py"],
    ["python", "scripts/reset_disposable_postgres.py"],
    ["alembic", "upgrade", "head"],
    ["alembic", "downgrade", "base"],
    ["alembic", "upgrade", "head"],
    [
        "python",
        "-m",
        "pytest",
        "tests/test_google_ads_read_only.py",
        "tests/test_api_v1_read_only.py",
        "tests/test_automation_foundation.py",
        "-k",
        "read_only or no_writes or no_product or pre_write",
    ],
    [
        "python",
        "-m",
        "pytest",
        "tests/test_google_ads_read_only.py",
        "tests/test_token_files.py",
        "tests/test_generate_google_ads_refresh_token.py",
        "tests/test_api_v1_read_only.py",
        "tests/test_automation_foundation.py",
        "-k",
        "read_only or token or secret or credential or sanitized or error_messages "
        "or controlled or approval",
    ],
    [
        "python",
        "-m",
        "pytest",
        "tests/test_api_v1_read_only.py",
        "tests/test_automation_foundation.py",
        "-k",
        "sanitized or secret or credential or token or error_messages or sensitive or search_term",
    ],
    [
        "python",
        "-m",
        "pytest",
        "tests/test_automation_foundation.py",
        "tests/test_api_v1_read_only.py",
        "-k",
        "automation_foundation or scoping or account_scoped or no_writes",
    ],
]

SHIM = r"""
import json, os, pathlib, subprocess, sys
name = pathlib.Path(sys.argv[0]).stem
if name == "python" and sys.argv[1:] == ["-"]:
    # Execute the real disposable-target guard (stdin); never connect to a DB.
    raise SystemExit(subprocess.run([os.environ["TRACE_REAL_PYTHON"], "-"], check=False).returncode)
trace = pathlib.Path(os.environ["TRACE_PATH"])
previous = trace.read_text().splitlines() if trace.exists() else []
with trace.open("a") as output:
    output.write(json.dumps({"argv": [name, *sys.argv[1:]],
        "database": os.environ.get("DATABASE_URL"),
        "pytest_options": os.environ.get("PYTEST_ADDOPTS"),
        "skip_nested": os.environ.get(
            "AD_ANALYZER_SKIP_NESTED_FULL_VALIDATION_REGRESSION")}) + "\n")
raise SystemExit(37 if len(previous) == int(os.environ["TRACE_FAIL_AT"]) else 0)
"""


def harness(tmp_path: Path, failure: int) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name in ("python", "alembic", "ruff", "mypy", "git"):
        shim = fake_bin / name
        if os.name == "nt":
            script = shim.with_suffix(".py")
            script.write_text(SHIM)
            shim.with_suffix(".cmd").write_text(f'@"{sys.executable}" "{script}" %*\n')
        else:
            shim.write_text(f"#!{sys.executable}\n" + SHIM)
            shim.chmod(0o755)
    trace = tmp_path / "commands.jsonl"
    return minimal_subprocess_env(
        {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "TRACE_REAL_PYTHON": sys.executable,
            "TRACE_PATH": str(trace),
            "TRACE_FAIL_AT": str(failure),
            "AD_ANALYZER_TEST_POSTGRES_URL": "postgresql+psycopg://localhost/orchestration_ci",
            "AD_ANALYZER_CI_DISPOSABLE_POSTGRES": "true",
            "AD_ANALYZER_DIFF_BASE": "fixture-base",
        }
    ), trace


@pytest.mark.parametrize("shell", ["bash", "powershell"])
@pytest.mark.parametrize("failure", [-1, *range(len(GATES))])
def test_full_gate_order_replay_and_failure_propagation(
    shell: str, failure: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = (bash_validate_command if shell == "bash" else powershell_validate_command)("Full")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    monkeypatch.setenv("AD_ANALYZER_SKIP_NESTED_FULL_VALIDATION_REGRESSION", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///must-not-inherit.db")
    env, trace = harness(tmp_path, failure)
    for _ in range(2 if failure == -1 else 1):
        trace.unlink(missing_ok=True)
        result = subprocess.run(
            command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=30, check=False
        )
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        assert result.returncode == (0 if failure == -1 else 37), result.stderr
        expected = GATES if failure == -1 else GATES[: failure + 1]
        assert [row["argv"] for row in rows] == expected
        assert all(row["database"] == env["AD_ANALYZER_TEST_POSTGRES_URL"] for row in rows)
        assert all(row["pytest_options"] is None and row["skip_nested"] is None for row in rows)
        assert sum(row["argv"] == ["python", "-m", "pytest"] for row in rows) <= 1
    assert os.environ["DATABASE_URL"] == "sqlite:///must-not-inherit.db"


def test_no_recursive_full_regression_remains() -> None:
    foundation = (ROOT / "tests/test_automation_foundation.py").read_text()
    assert 'validate_command("Full")' not in foundation
    assert "SKIP_NESTED_FULL" not in foundation
    assert (
        "test_migration_validation_repairs_head_state_with_missing_application_tables" in foundation
    )
    assert "test_postgresql_tests_followed_by_migration_validation_succeed" in foundation


def test_ci_preserves_required_aggregate_and_downstream_gates() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "name: Validation" in workflow
    assert workflow.count("run: python -m pytest -ra --basetemp") == 1
    aggregate = workflow.index("run: python -m pytest -ra --basetemp")
    for gate in ("Migrations", "ReadOnly", "Security", "Privacy", "Focused"):
        assert workflow.index(f"run: ./scripts/validate.sh {gate}") > aggregate
    for gate in ("run: ruff check .", "run: mypy", "Fast bounded orchestration feedback"):
        assert workflow.index(gate) < aggregate
    assert "run: ./scripts/validate.sh PostgreSQL" in workflow
    assert "git diff --check" in workflow
    assert "SKIP_NESTED_FULL" not in workflow
    assert "continue-on-error" not in workflow
    assert "timeout-minutes: 90" in workflow and "timeout-minutes: 120" in workflow
    assert "cache: npm" in workflow and "cache: pip" in workflow
    assert "cache-dependency-path: browser/auth/package-lock.json" in workflow
    assert "branches: [main, 'codex/inlet-*']" in workflow
    assert "push:\n    branches: [main]" in workflow
    assert "workflow_dispatch:" in workflow
    for filename in ("ci.yml", "operations-code-validation.yml"):
        value = (ROOT / ".github/workflows" / filename).read_text()
        assert "github.event_name == 'workflow_dispatch' && github.run_id" in value
        assert "github.event.pull_request.number || github.ref" in value
        assert "github.workflow" in value
        assert "cancel-in-progress: true" in value
