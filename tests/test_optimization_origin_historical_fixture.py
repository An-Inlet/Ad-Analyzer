"""Historical mapper teardown must restore even application aliases imported later."""

import sys
from types import ModuleType

import pytest
from app.publication import execution_models
from sqlalchemy import create_engine, inspect, text

from tests.optimization_origin_historical_schema import install_legacy_origin


def test_historical_mapper_restores_late_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    original = execution_models.ProviderExecutionRevision
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as db:
            db.execute(
                text(
                    "CREATE TABLE provider_execution_revisions "
                    "(mandate_id TEXT NOT NULL, revision INTEGER NOT NULL, "
                    "PRIMARY KEY(mandate_id, revision))"
                )
            )
        with pytest.MonkeyPatch.context() as scope:
            cleanup = install_legacy_origin(scope, engine)
            legacy = execution_models.ProviderExecutionRevision
            late = ModuleType("app._historical_fixture_late_import")
            late.revision = legacy  # type: ignore[attr-defined]
            sentinel = object()
            late.unrelated = sentinel  # type: ignore[attr-defined]
            monkeypatch.setitem(sys.modules, late.__name__, late)
            try:
                row = legacy(
                    mandate_id="a" * 32,
                    revision=1,
                    origin_kind="legacy",
                    origin_preparation_digest=None,
                )
                assert row.origin_kind == "legacy" and row.origin_preparation_digest is None
                with pytest.raises(ValueError, match="cannot contain marked origin"):
                    legacy(
                        mandate_id="a" * 32,
                        revision=2,
                        origin_kind="optimization_customer_v1",
                        origin_preparation_digest="b" * 64,
                    )
                with pytest.raises(AttributeError):
                    row.origin_kind = "optimization_customer_v1"
            finally:
                cleanup()
            assert late.revision is original
            assert late.unrelated is sentinel
            assert execution_models.ProviderExecutionRevision is original
            assert inspect(legacy, raiseerr=False) is None
            assert inspect(original).columns.origin_kind is not None
        assert execution_models.ProviderExecutionRevision is original
    finally:
        engine.dispose()
