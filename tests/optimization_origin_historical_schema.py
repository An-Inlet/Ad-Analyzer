"""Explicit pre0080 revision mapping for historical migration fixtures only."""

import sys
from collections.abc import Callable

import pytest
from app.publication.execution_models import ProviderExecutionRevision
from sqlalchemy import Engine, MetaData, Table, inspect
from sqlalchemy.orm import registry


def install_legacy_origin(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> Callable[[], None]:
    """Reflect real historical columns; return cleanup including late-loaded aliases."""
    inspector = inspect(engine)
    assert "optimization_mandate_preparations" not in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("provider_execution_revisions")}
    assert not {"origin_kind", "origin_preparation_digest"}.intersection(columns)
    from app.publication import execution_models

    assert execution_models.ProviderExecutionRevision is ProviderExecutionRevision

    class LegacyRevision:
        @property
        def origin_kind(self) -> str:
            return "legacy"

        @property
        def origin_preparation_digest(self) -> None:
            return None

    table = Table("provider_execution_revisions", MetaData(), autoload_with=engine)
    mapping = registry()
    mapping.map_imperatively(LegacyRevision, table)
    for name, module in tuple(sys.modules.items()):
        if name.startswith("app.") and module is not None:
            for attribute, value in tuple(vars(module).items()):
                if value is ProviderExecutionRevision:
                    monkeypatch.setattr(module, attribute, LegacyRevision)

    def cleanup() -> None:
        # Include module-level imports that happened AFTER the initial patch scan.
        # No application's current mapper or global metadata is ever disposed.
        for name, module in tuple(sys.modules.items()):
            if name.startswith("app.") and module is not None:
                for attribute, value in tuple(vars(module).items()):
                    if value is LegacyRevision:
                        setattr(module, attribute, ProviderExecutionRevision)
        mapping.dispose()

    return cleanup


@pytest.fixture
def legacy_origin(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Callable[[Engine], None]:
    """Install only after a test establishes its actual pre0080 physical schema."""
    installed = False

    def install(engine: Engine) -> None:
        nonlocal installed
        assert not installed, "historical mapper must have one explicit schema scope"
        cleanup = install_legacy_origin(monkeypatch, engine)
        request.addfinalizer(cleanup)
        installed = True

    return install
