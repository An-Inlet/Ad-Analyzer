"""Every declared model participates in the migration/runtime metadata graph."""

import ast
import subprocess
import sys
from pathlib import Path

from app.database.models import GUARD_MODULES, MODEL_MODULES, register_models
from app.database.session import Base


def test_registry_covers_every_model_module() -> None:
    root = Path(__file__).resolve().parents[1]
    declared = {
        ".".join(path.relative_to(root).with_suffix("").parts)
        for path in (root / "app").rglob("*.py")
        if any(
            isinstance(node, ast.ClassDef)
            and any(isinstance(base, ast.Name) and base.id == "Base" for base in node.bases)
            for node in ast.walk(ast.parse(path.read_text()))
        )
    }
    assert set(MODEL_MODULES) == declared
    assert len(MODEL_MODULES) == len(set(MODEL_MODULES))


def test_registration_is_idempotent_and_includes_cross_domain_foreign_keys() -> None:
    metadata = register_models()
    assert metadata is Base.metadata
    assert register_models() is metadata
    for table, target in (
        ("web_analytics_events", "ad_groups"),
        ("publication_plans", "mandate_actions"),
    ):
        assert target in {fk.column.table.name for fk in metadata.tables[table].foreign_keys}


def test_registered_provider_evidence_has_protected_scoped_lifecycle_policy() -> None:
    from app.lifecycle.inventory import verify_registry
    from app.lifecycle.registry import TABLES

    register_models()
    verify_registry()
    for name, omitted in (
        ("provider_qualifications", {"evidence"}),
        ("provider_reviews", {"review", "plan"}),
        ("provider_review_approvals", set()),
    ):
        policy = TABLES[name]
        assert policy.scope == "workspace"
        assert policy.protected
        assert "workspace_id" in policy.fields
        assert not omitted.intersection(policy.fields)


def test_required_metadata_guards_remain_registered() -> None:
    assert GUARD_MODULES == ("app.commerce.acquisition_guards",)
    assert not set(GUARD_MODULES).intersection(MODEL_MODULES)
    # A fresh process proves registration installs the listener without the test
    # accidentally importing and installing it first.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from sqlalchemy import event; "
            "from app.database.models import register_models; "
            "metadata = register_models(); "
            "guard = sys.modules['app.commerce.acquisition_guards']; "
            "assert event.contains(metadata, 'after_create', guard.install); "
            "assert register_models() is metadata; "
            "assert event.contains(metadata, 'after_create', guard.install)",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
