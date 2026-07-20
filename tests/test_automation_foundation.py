from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"
VALIDATE_SH = ROOT / "scripts" / "validate.sh"
VALIDATE_PS1 = ROOT / "scripts" / "validate.ps1"
ROADMAP = ROOT / "docs" / "project-roadmap.md"
PHASE8_SUPPLEMENT = ROOT / "docs" / "phase8-roadmap.md"
POLICY = ROOT / "docs" / "automation-policy.md"
DECISIONS = ROOT / "docs" / "decision-register.md"
DONE = ROOT / "docs" / "definition-of-done.md"
CONTROLLER = ROOT / "docs" / "project-controller.md"
GITHUB_SETUP = ROOT / "docs" / "github-automation-setup.md"


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


def test_phase8_only_document_is_not_complete_project_roadmap() -> None:
    supplement = read(PHASE8_SUPPLEMENT)
    assert "supplement only" in supplement
    assert "must not be treated as the complete project roadmap" in supplement
    assert "docs/project-roadmap.md" in supplement


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

    for premature_scope in ("ControlledWrites", "Release"):
        result = subprocess.run(
            ["bash", str(VALIDATE_SH), premature_scope],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        assert result.returncode != 0
        assert "not implemented" in result.stderr


def test_destructive_migration_validation_rejects_unsafe_database_targets() -> None:
    result = subprocess.run(
        ["bash", str(VALIDATE_SH), "Migrations"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={"DENTICODE_TEST_POSTGRES_URL": "postgresql+psycopg://localhost/denticode_ads_optimizer"},
    )
    assert result.returncode != 0
    assert "Refusing migration validation" in result.stderr


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


def test_read_only_boundary_can_evolve_for_phase11_controlled_writes() -> None:
    shell = read(VALIDATE_SH)
    workflow = read(CI)
    assert "DENTICODE_PROJECT_PHASE: pre-controlled-writes" in workflow
    assert "ControlledWrites gates are intentionally not implemented before Phase 11" in shell
    assert "ReadOnly" in shell


def test_no_product_functionality_is_added_in_infrastructure_pr() -> None:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD^", "--", "app", "migrations/versions"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert result.stdout == ""
