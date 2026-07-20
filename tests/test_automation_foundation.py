from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"
VALIDATE_SH = ROOT / "scripts" / "validate.sh"
VALIDATE_PS1 = ROOT / "scripts" / "validate.ps1"
RESET_POSTGRES = ROOT / "scripts" / "reset_disposable_postgres.py"
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
ROADMAP = ROOT / "docs" / "project-roadmap.md"
PHASE8_SUPPLEMENT = ROOT / "docs" / "phase8-roadmap.md"
POLICY = ROOT / "docs" / "automation-policy.md"
DECISIONS = ROOT / "docs" / "decision-register.md"
DONE = ROOT / "docs" / "definition-of-done.md"
CONTROLLER = ROOT / "docs" / "project-controller.md"
GITHUB_SETUP = ROOT / "docs" / "github-automation-setup.md"


def resolve_bash() -> str | None:
    return shutil.which("bash")


def resolve_powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def minimal_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", ""), "NO_COLOR": "1", "TERM": "dumb"}
    for name in (
        "SystemRoot",
        "ComSpec",
        "PATHEXT",
        "PSModulePath",
        "POWERSHELL_TELEMETRY_OPTOUT",
        "VIRTUAL_ENV",
        "HOME",
        "USERPROFILE",
        "TMP",
        "TEMP",
    ):
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    if extra:
        env.update(extra)
    return env


def strip_ansi(value: str) -> str:
    return ANSI_ESCAPE.sub("", value)


def normalize_powershell_output(value: str) -> str:
    value = strip_ansi(value)
    value = re.sub(r"(?m)^\s*\|\s?", " ", value)
    return " ".join(value.split())


def validate_command(scope: str) -> list[str]:
    if os.name == "nt":
        powershell = resolve_powershell()
        if powershell is None:
            pytest.skip("PowerShell is unavailable on this platform")
        return [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(VALIDATE_PS1),
            "-Scope",
            scope,
        ]

    bash = resolve_bash()
    if bash is None:
        pytest.skip("bash is unavailable on this platform")
    return [bash, str(VALIDATE_SH), scope]


def bash_validate_command(scope: str) -> list[str]:
    bash = resolve_bash()
    if bash is None:
        pytest.skip("bash is unavailable on this platform")
    return [bash, str(VALIDATE_SH), scope]


def powershell_validate_command(scope: str) -> list[str]:
    powershell = resolve_powershell()
    if powershell is None:
        pytest.skip("PowerShell is unavailable on this platform")
    return [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(VALIDATE_PS1),
        "-Scope",
        scope,
    ]


def reset_helper_command() -> list[str]:
    return [sys.executable, str(RESET_POSTGRES)]


def disposable_postgres_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    url = os.environ.get("DENTICODE_TEST_POSTGRES_URL")
    marker = os.environ.get("DENTICODE_CI_DISPOSABLE_POSTGRES")
    if not url or marker != "true":
        pytest.skip(
            "DENTICODE_TEST_POSTGRES_URL and DENTICODE_CI_DISPOSABLE_POSTGRES=true "
            "are required for disposable PostgreSQL integration tests"
        )
    env = minimal_subprocess_env(
        {
            "DENTICODE_TEST_POSTGRES_URL": url,
            "DENTICODE_CI_DISPOSABLE_POSTGRES": "true",
        }
    )
    if extra:
        env.update(extra)
    return env


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_master_roadmap_includes_all_remaining_phases() -> None:
    roadmap = read(ROADMAP)
    for phase in (
        "Phase 8 — Read-only analytics",
        "Phase 9 — Recommendation generation",
        "Phase 10 — Approval and audit workflow",
        "Phase 11 — Controlled Google Ads execution",
        "Phase 12 — Production hardening",
    ):
        assert phase in roadmap
    for field in (
        "identifier:",
        "branch name:",
        "explicit exclusions:",
        "security gates:",
        "privacy gates:",
        "rollback requirements:",
        "acceptance criteria:",
    ):
        assert field in roadmap
    assert "Only one dependent implementation PR may be open at a time" in roadmap
    assert "migrations: none; do not add read-only tables in PR 8.1" in roadmap
    assert "8.2 — Repository aggregation and query safety" in roadmap
    assert "8.3 — Deterministic findings service and API" in roadmap
    assert "explicit exclusions: dashboard routes, templates, CSS" in roadmap
    assert "8.4 — Dashboard analytics views" in roadmap
    assert "explicit exclusions: new API endpoints" in roadmap


def test_phase8_only_document_is_not_complete_project_roadmap() -> None:
    supplement = read(PHASE8_SUPPLEMENT)
    assert "supplement only" in supplement
    assert "must not be treated as the complete project roadmap" in supplement
    assert "docs/project-roadmap.md" in supplement
    assert "No database migration and no read-only tables" in supplement
    assert "Dashboard analytics views" in supplement


def test_automation_policy_is_project_wide_and_requires_human_gates() -> None:
    policy = read(POLICY)
    for requirement in (
        "governs every remaining Denticode Ads Optimizer phase",
        "Every branch starts from latest `main`",
        "Never write directly to `main`",
        "one dependent product PR open at a time",
        "No Google Ads writes before Phase 11 controlled execution",
        "No live writes without explicit approved policy and human authorization",
        "No production deployment without a human release gate",
        "Do not bypass required checks",
        "No destructive migration against local development, staging, or production",
        "Use squash merge",
    ):
        assert requirement in policy


def test_project_wide_documents_exist() -> None:
    for path in (DECISIONS, DONE, CONTROLLER, GITHUB_SETUP):
        assert path.exists(), f"missing {path.relative_to(ROOT)}"


def test_decision_register_contains_required_decisions() -> None:
    register = read(DECISIONS)
    for decision in (
        "analytics thresholds",
        "metric availability by entity level",
        "search-term display and redaction",
        "finding and recommendation severity policy",
        "executable recommendation types",
        "Google Ads mutation allowlist",
        "human approval requirements",
        "account allowlists",
        "stale recommendation expiration",
        "rollback expectations",
        "hosting platform",
        "managed PostgreSQL provider",
        "secrets manager",
        "monitoring and alert destinations",
        "backup retention",
        "production release criteria",
    ):
        assert decision in register
    for field in ("Decision ID", "Affected phase", "Status", "Blocking", "Available options"):
        assert field in register


def test_definition_of_done_contains_pr_and_production_gates() -> None:
    done = read(DONE)
    for gate in (
        "Approved scope implemented",
        "PostgreSQL tests pass",
        "Reversible migrations are tested only on disposable PostgreSQL",
        "Account isolation is verified",
        "Human approval present when required",
        "Analytics works on synchronized data",
        "All live writes require approved controls",
        "Restore procedure is tested",
        "Release approval is recorded",
    ):
        assert gate in done


def test_project_controller_cannot_bypass_human_approval() -> None:
    controller = read(CONTROLLER)
    assert "must not approve its own work" in controller
    assert "Never approve your own work" in controller
    assert "Stop for product, privacy, security, architecture" in controller
    assert (
        "starts only the next unblocked roadmap PR" in controller
        or "Start only the next unblocked roadmap PR" in controller
    )


def test_github_setup_requires_protected_human_review() -> None:
    setup = read(GITHUB_SETUP)
    for requirement in (
        "Require at least one human approval",
        "dismissal of stale approvals",
        "Require branches to be up to date",
        "Validation",
        "Require conversation resolution",
        "Block force pushes",
        "Block branch deletion",
        "enable squash merge",
        "Enable auto-merge",
        "do not count Codex as the required human approval",
        "cannot bypass the `main` ruleset",
    ):
        assert requirement in setup


def test_validation_scripts_propagate_failures_and_support_all_scopes() -> None:
    shell = read(VALIDATE_SH)
    powershell = read(VALIDATE_PS1)
    for scope in (
        "Full",
        "Focused",
        "PostgreSQL",
        "Migrations",
        "Security",
        "Privacy",
        "ReadOnly",
        "ControlledWrites",
        "Release",
    ):
        assert scope in shell
        assert scope in powershell
    assert "set -euo pipefail" in shell
    assert "$ErrorActionPreference = 'Stop'" in powershell
    assert "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }" in powershell
    for substantive_command in (
        "tests/test_api_v1_read_only.py",
        "tests/test_google_ads_read_only.py",
        "tests/test_token_files.py",
        "tests/test_generate_google_ads_refresh_token.py",
        "tests/test_phase7_postgres_transactions.py",
    ):
        assert substantive_command in shell

    assert "release_validation()" in shell
    controlled_result = subprocess.run(
        validate_command("ControlledWrites"),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert controlled_result.returncode == 0
    assert "tests/test_analyzer_v1.py" in shell


def test_destructive_migration_validation_rejects_unsafe_database_targets() -> None:
    result = subprocess.run(
        validate_command("Migrations"),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=minimal_subprocess_env({
            "DENTICODE_TEST_POSTGRES_URL": "postgresql+psycopg://localhost/denticode_ads_optimizer",
        }),
    )
    assert result.returncode != 0
    assert "Refusing migration validation" in result.stderr


def test_disposable_postgres_validation_requires_marker_and_database_name() -> None:
    shell = read(VALIDATE_SH)
    powershell = read(VALIDATE_PS1)
    for contents in (shell, powershell):
        assert "DENTICODE_CI_DISPOSABLE_POSTGRES must exactly equal true" in contents
        assert "database name must use a controlled _ci or _test naming convention" in contents
        assert "staging/production database names are never disposable" in contents
        assert "DATABASE_URL" in contents
        assert "DENTICODE_TEST_POSTGRES_URL" in contents
    assert "urlparse" in shell
    assert "System.Uri" in powershell


def test_bash_disposable_postgres_validation_accepts_ci_database_until_connection() -> None:
    raw_url = "postgresql+psycopg://postgres:postgres@127.0.0.1:1/denticode_ads_optimizer_ci"
    result = subprocess.run(
        bash_validate_command("Migrations"),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=minimal_subprocess_env(
            {
                "DENTICODE_CI_DISPOSABLE_POSTGRES": "true",
                "DENTICODE_TEST_POSTGRES_URL": raw_url,
            }
        ),
    )
    assert result.returncode != 0
    assert "+ python scripts/reset_disposable_postgres.py" in result.stdout
    assert "+ alembic upgrade head" not in result.stdout
    assert "Refusing migration validation" not in result.stderr
    assert "Disposable PostgreSQL schema reset failed" in result.stderr
    assert "postgres:postgres" not in result.stderr
    assert raw_url not in result.stderr


def test_bash_disposable_postgres_validation_rejects_marker_without_ci_database() -> None:
    env = minimal_subprocess_env({
        "DENTICODE_CI_DISPOSABLE_POSTGRES": "true",
        "DENTICODE_TEST_POSTGRES_URL": (
            "postgresql+psycopg://postgres:postgres@localhost:5432/"
            "denticode_ads_optimizer"
        ),
    })
    result = subprocess.run(
        bash_validate_command("Migrations"),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    assert result.returncode != 0
    assert "controlled _ci or _test naming convention" in result.stderr


def test_bash_disposable_postgres_validation_rejects_ci_name_without_marker() -> None:
    env = minimal_subprocess_env({
        "DENTICODE_TEST_POSTGRES_URL": (
            "postgresql+psycopg://postgres:postgres@localhost:5432/"
            "denticode_ads_optimizer_ci"
        ),
    })
    result = subprocess.run(
        bash_validate_command("Migrations"),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    assert result.returncode != 0
    assert "DENTICODE_CI_DISPOSABLE_POSTGRES must exactly equal true" in result.stderr


def test_powershell_premature_controlled_writes_and_release_fail_closed() -> None:
    for premature_scope in ("ControlledWrites", "Release"):
        result = subprocess.run(
            powershell_validate_command(premature_scope),
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
            env=minimal_subprocess_env(),
        )
        assert result.returncode != 0
        assert "not implemented" in normalize_powershell_output(result.stderr)


def test_normalize_powershell_output_preserves_wrapped_semantic_messages() -> None:
    staging_sample = (
        "\x1b[31;1mWrite-Error: \x1b[0m\n"
        "\x1b[31;1m| Refusing migration validation: staging/production database names are\x1b[0m\n"
        "\x1b[31;1m| never disposable.\x1b[0m\n"
    )
    controlled_name_sample = (
        "\x1b[31;1mWrite-Error: \x1b[0m\n"
        "\x1b[31;1m| Refusing migration validation: database name must use a "
        "controlled _ci\x1b[0m\n"
        "\x1b[31;1m| or _test naming convention.\x1b[0m\n"
    )

    assert (
        "staging/production database names are never disposable"
        in normalize_powershell_output(staging_sample)
    )
    assert (
        "controlled _ci or _test naming convention"
        in normalize_powershell_output(controlled_name_sample)
    )


@pytest.mark.parametrize(
    ("env_overrides", "expected_error"),
    (
        (
            {
                "DENTICODE_CI_DISPOSABLE_POSTGRES": "true",
                "DENTICODE_TEST_POSTGRES_URL": (
                    "postgresql+psycopg://postgres:postgres@localhost:5432/"
                    "denticode_ads_optimizer_prod"
                ),
            },
            "staging/production database names are never disposable",
        ),
        (
            {
                "DENTICODE_CI_DISPOSABLE_POSTGRES": "true",
                "DENTICODE_TEST_POSTGRES_URL": (
                    "postgresql+psycopg://postgres:postgres@localhost:5432/"
                    "denticode_ads_optimizer_staging"
                ),
            },
            "staging/production database names are never disposable",
        ),
        (
            {
                "DENTICODE_CI_DISPOSABLE_POSTGRES": "true",
                "DENTICODE_TEST_POSTGRES_URL": (
                    "postgresql+psycopg://postgres:postgres@localhost:5432/"
                    "denticode_ads_optimizer"
                ),
            },
            "controlled _ci or _test naming convention",
        ),
        (
            {
                "DENTICODE_TEST_POSTGRES_URL": (
                    "postgresql+psycopg://postgres:postgres@localhost:5432/"
                    "denticode_ads_optimizer_ci"
                ),
            },
            "DENTICODE_CI_DISPOSABLE_POSTGRES must exactly equal true",
        ),
    ),
)
def test_powershell_disposable_postgres_guard_rejects_unsafe_targets(
    env_overrides: dict[str, str], expected_error: str
) -> None:
    result = subprocess.run(
        powershell_validate_command("Migrations"),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=minimal_subprocess_env(env_overrides),
    )
    normalized_stdout = normalize_powershell_output(result.stdout)
    normalized_stderr = normalize_powershell_output(result.stderr)
    assert result.returncode != 0
    assert expected_error in normalized_stderr
    raw_url = env_overrides.get("DENTICODE_TEST_POSTGRES_URL", "")
    for output in (result.stdout, result.stderr, normalized_stdout, normalized_stderr):
        assert "postgres:postgres" not in output
        if raw_url:
            assert raw_url not in output


def test_powershell_disposable_postgres_guard_accepts_ci_database_until_connection() -> None:
    raw_url = "postgresql+psycopg://postgres:postgres@127.0.0.1:1/denticode_ads_optimizer_ci"
    result = subprocess.run(
        powershell_validate_command("Migrations"),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=minimal_subprocess_env(
            {
                "DENTICODE_CI_DISPOSABLE_POSTGRES": "true",
                "DENTICODE_TEST_POSTGRES_URL": raw_url,
            }
        ),
    )
    normalized_stdout = normalize_powershell_output(result.stdout)
    normalized_stderr = normalize_powershell_output(result.stderr)
    assert result.returncode != 0
    assert "+ python scripts/reset_disposable_postgres.py" in normalized_stdout
    assert "+ alembic upgrade head" not in normalized_stdout
    assert "Refusing migration validation" not in normalized_stderr
    assert "Disposable PostgreSQL schema reset failed" in normalized_stderr
    for output in (result.stdout, result.stderr, normalized_stdout, normalized_stderr):
        assert "postgres:postgres" not in output
        assert raw_url not in output


def test_powershell_child_command_failures_propagate_nonzero_exit_codes(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_python = fake_bin / ("python.cmd" if os.name == "nt" else "python")
    fake_python.write_text(
        "@exit 37\n" if os.name == "nt" else "#!/usr/bin/env sh\nexit 37\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    result = subprocess.run(
        powershell_validate_command("Focused"),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=minimal_subprocess_env({"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"}),
    )
    assert result.returncode == 37


def test_reset_disposable_postgres_rejects_missing_marker() -> None:
    result = subprocess.run(
        reset_helper_command(),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=minimal_subprocess_env(
            {"DENTICODE_TEST_POSTGRES_URL": "postgresql+psycopg://user:secret@localhost/db_ci"}
        ),
    )
    assert result.returncode != 0
    assert "DENTICODE_CI_DISPOSABLE_POSTGRES must exactly equal true" in result.stderr
    assert "secret" not in result.stderr
    assert "postgresql+psycopg://" not in result.stderr


@pytest.mark.parametrize(
    ("url", "expected_error"),
    (
        (
            "postgresql+psycopg://user:secret@localhost/denticode_ads_optimizer",
            "controlled _ci or _test naming convention",
        ),
        (
            "postgresql+psycopg://user:secret@localhost/denticode_ads_optimizer_staging_ci",
            "staging/production database names are never disposable",
        ),
        (
            "postgresql+psycopg://user:secret@localhost/denticode_ads_optimizer_prod_test",
            "staging/production database names are never disposable",
        ),
        ("not a url", "DENTICODE_TEST_POSTGRES_URL must use a PostgreSQL scheme"),
        ("postgresql+psycopg://[bad", "malformed DENTICODE_TEST_POSTGRES_URL"),
        ("postgresql+psycopg://localhost/", "PostgreSQL database name is empty"),
        ("sqlite:///denticode_ads_optimizer_ci", "must use a PostgreSQL scheme"),
    ),
)
def test_reset_disposable_postgres_rejects_unsafe_urls_without_exposing_credentials(
    url: str, expected_error: str
) -> None:
    result = subprocess.run(
        reset_helper_command(),
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=minimal_subprocess_env(
            {
                "DENTICODE_CI_DISPOSABLE_POSTGRES": "true",
                "DENTICODE_TEST_POSTGRES_URL": url,
            }
        ),
    )
    assert result.returncode != 0
    assert expected_error in result.stderr
    assert "secret" not in result.stderr
    assert url not in result.stderr


def test_validation_scripts_invoke_reset_before_migration_upgrade() -> None:
    for script in (read(VALIDATE_SH), read(VALIDATE_PS1)):
        reset_index = script.index("python scripts/reset_disposable_postgres.py")
        upgrade_index = script.index("alembic upgrade head")
        assert reset_index < upgrade_index
        assert "DATABASE_URL" in script
        assert "DENTICODE_TEST_POSTGRES_URL" in script


def test_migration_validation_repairs_head_state_with_missing_application_tables() -> None:
    pytest.importorskip("psycopg")
    from app.ads import models as ads_models  # noqa: F401
    from app.database.session import Base
    from sqlalchemy import create_engine, text

    assert any(table.name == "job_runs" for table in Base.metadata.tables.values())

    command = validate_command("Migrations")
    env = disposable_postgres_env()
    subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    engine = create_engine(env["DENTICODE_TEST_POSTGRES_URL"])
    try:
        Base.metadata.drop_all(engine)
        with engine.connect() as connection:
            version = connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert version is not None
            job_runs_exists = connection.scalar(text("SELECT to_regclass('public.job_runs')"))
            assert job_runs_exists is None
    finally:
        engine.dispose()

    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0


def test_postgresql_tests_followed_by_migration_validation_succeed() -> None:
    migration_command = validate_command("Migrations")
    env = disposable_postgres_env()
    subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_phase7_postgres_transactions.py", "-q"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        migration_command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )


def test_full_validation_can_run_twice_against_same_disposable_database() -> None:
    if os.environ.get("DENTICODE_SKIP_NESTED_FULL_VALIDATION_REGRESSION") == "true":
        pytest.skip("nested Full validation regression test is disabled")
    command = validate_command("Full")
    env = disposable_postgres_env({"DENTICODE_SKIP_NESTED_FULL_VALIDATION_REGRESSION": "true"})
    for _ in range(2):
        subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )


def test_ci_uses_disposable_postgresql_and_project_wide_gates() -> None:
    workflow = read(CI)
    assert "postgres:16" in workflow
    assert "POSTGRES_DB: denticode_ads_optimizer_ci" in workflow
    assert "DENTICODE_CI_DISPOSABLE_POSTGRES: \"true\"" in workflow
    assert "DENTICODE_TEST_POSTGRES_URL:" in workflow
    assert "./scripts/validate.sh PostgreSQL" in workflow
    assert "./scripts/validate.sh Migrations" in workflow
    assert "./scripts/validate.sh ReadOnly" in workflow
    assert "./scripts/validate.sh Security" in workflow
    assert "./scripts/validate.sh Privacy" in workflow
    assert "./scripts/validate.sh Focused" in workflow
    assert "permissions:" in workflow
    assert "contents: read" in workflow
    assert "actions/checkout@v4" in workflow
    assert "fetch-depth: 0" in workflow
    assert "actions/setup-python@v5" in workflow
    assert "x-access-token" not in workflow
    assert "git init" not in workflow
    assert "git fetch --no-tags --prune --depth=0" not in workflow
    assert "git diff --check \"origin/${{ github.base_ref }}...HEAD\"" in workflow


def test_read_only_boundary_can_evolve_for_phase11_controlled_writes() -> None:
    shell = read(VALIDATE_SH)
    workflow = read(CI)
    assert "DENTICODE_PROJECT_PHASE: pre-controlled-writes" in workflow
    assert "ControlledWrites gates are intentionally not implemented before Phase 11" in shell
    assert "settings.google_ads_write_enabled is False" in shell
    assert "ReadOnly" in shell


def test_pre_write_modules_do_not_log_sensitive_search_terms_or_call_mutations() -> None:
    forbidden_fragments = (
        "logger.info(search_term",
        "logger.debug(search_term",
        "print(search_term",
        ".mutate(",
        "upload_click_conversions",
        "GoogleAdsService.Mutate",
    )
    checked_roots = (ROOT / "app" / "api", ROOT / "app" / "dashboard", ROOT / "app" / "optimizer")
    for root in checked_roots:
        for path in root.rglob("*.py"):
            contents = read(path)
            for fragment in forbidden_fragments:
                assert fragment not in contents, f"{path.relative_to(ROOT)} contains {fragment}"


def test_workflow_uses_official_actions_without_token_bearing_checkout() -> None:
    workflow = read(CI)
    assert "actions/checkout@v4" in workflow
    assert "fetch-depth: 0" in workflow
    assert "actions/setup-python@v5" in workflow
    assert "GH_TOKEN" not in workflow
    assert "x-access-token" not in workflow
    assert "refs/pull" not in workflow



def resolve_product_diff_base() -> str:
    configured = os.environ.get("DENTICODE_DIFF_BASE")
    if configured:
        return configured
    origin_main = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if origin_main.returncode == 0:
        return "origin/main"

    first_added = subprocess.run(
        [
            "git",
            "log",
            "--diff-filter=A",
            "--reverse",
            "--format=%H",
            "--",
            ".github/workflows/ci.yml",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()
    assert first_added, "cannot resolve local automation branch base"
    return f"{first_added[0]}^"


def test_no_product_functionality_is_added_in_infrastructure_pr() -> None:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            f"{resolve_product_diff_base()}...HEAD",
            "--",
            "app",
            "migrations/versions",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert result.stdout == ""
