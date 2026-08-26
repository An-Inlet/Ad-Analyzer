import re
from pathlib import Path

PLATFORM_SURFACES = (
    ".env.example",
    ".github/workflows/ci.yml",
    ".github/workflows/deploy-ad-analyzer-web.yml",
    ".github/workflows/production-operations-audit.yml",
    "Dockerfile",
    "alembic.ini",
    "app/dashboard/templates/base.html",
    "app/main.py",
    "app/settings.py",
    "deploy/docker-compose.yml",
    "deploy/managed-environment.example.yml",
    "docs/deployment-architecture.md",
    "docs/managed-infrastructure-configuration.md",
    "docs/operations-automation.md",
    "docs/operations/runbook.md",
    "docs/platform-name-cutover.md",
    "infra/gcp/main.tf",
    "scripts/bootstrap_github_operations.ps1",
    "scripts/cloud_run_web_start.py",
    "scripts/prepare_cloud_run_cutover.py",
    "scripts/production_ops_audit.py",
    "scripts/production_ops_audit_entrypoint.py",
)

CLIENT_STEM = "Denti" + "code"
FORBIDDEN_PLATFORM_PATTERNS = (
    re.compile(CLIENT_STEM + r" Ads Optimizer"),
    re.compile(r"Konner-An-Inlet/" + CLIENT_STEM + r"-Ads-Optimizer"),
    re.compile(CLIENT_STEM.upper() + "_"),
    re.compile(CLIENT_STEM.lower() + r"_(?:ads_optimizer|app)\b"),
    re.compile(
        CLIENT_STEM.lower()
        + r"-(?:web|sync|migration|github|deployer|scheduler|migrations|"
        + r"ads-optimizer|analyzer-postgres)\b"
    ),
    re.compile(r"codex/complete-" + CLIENT_STEM.lower() + r"-ads-analyzer-buildout"),
)


def test_platform_surfaces_use_only_neutral_identifiers() -> None:
    for path_string in PLATFORM_SURFACES:
        path = Path(path_string)
        content = path.read_text()

        for pattern in FORBIDDEN_PLATFORM_PATTERNS:
            assert pattern.search(content) is None, (
                f"{path} contains legacy platform identifier matching {pattern.pattern!r}"
            )


def test_dashboard_brand_is_platform_neutral() -> None:
    base_template = Path("app/dashboard/templates/base.html").read_text()

    assert "<title>{{ title }} | Ad Analyzer</title>" in base_template
    assert '<a href="/dashboard">Ad Analyzer</a>' in base_template
    assert "Denticode" not in base_template


def test_settings_use_neutral_environment_and_repository_names() -> None:
    settings = Path("app/settings.py").read_text()

    assert 'validation_alias="AD_ANALYZER_API_TOKEN"' in settings
    assert 'default="Konner-An-Inlet/Ad-Analyzer"' in settings


def test_client_workspace_identity_remains_scoped_to_client_data() -> None:
    readme = Path("README.md").read_text()
    workspace_migration = Path(
        "migrations/versions/20260802_0008_ad_analyzer_workspaces.py"
    ).read_text()

    assert "Denticode Ad Analyzer workspace" in readme
    assert '"slug": "denticode"' in workspace_migration
    assert '"client_name": "Denticode"' in workspace_migration
