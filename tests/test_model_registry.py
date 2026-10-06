"""Every declared model participates in the migration/runtime metadata graph."""

import ast
from pathlib import Path

from app.database.models import MODEL_MODULES, register_models
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
