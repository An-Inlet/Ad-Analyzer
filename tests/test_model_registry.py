"""Every declared model participates in the migration/runtime metadata graph."""

from pathlib import Path

from app.database.models import MODEL_MODULES, register_models
from app.database.session import Base


def test_registry_covers_every_model_module() -> None:
    root = Path(__file__).resolve().parents[1]
    declared = {
        ".".join(path.relative_to(root).with_suffix("").parts)
        for path in (root / "app").rglob("models.py")
        if path != root / "app/database/models.py"
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
