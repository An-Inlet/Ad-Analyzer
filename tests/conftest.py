"""Register ORM models and explicit retained-engine test isolation."""

import pytest
from app import advertising_capabilities
from app.database.models import register_models

register_models()


@pytest.fixture
def retained_execution_engine(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit historical engine regression only; never an MVP capability."""
    if request.node.get_closest_marker("retained_execution") is None:
        pytest.fail("retained execution fixture requires explicit historical marker")
    if request.node.get_closest_marker("planning_boundary") is not None:
        pytest.fail("planning boundary tests cannot enable retained execution")
    monkeypatch.setattr(advertising_capabilities, "require_advertising_write", lambda: None)
    monkeypatch.setattr(advertising_capabilities, "advertising_writes_enabled", lambda: True)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.get_closest_marker("planning_boundary") is not None and (
            item.get_closest_marker("retained_execution") is not None
            or "retained_execution_engine" in getattr(item, "fixturenames", ())
        ):
            raise pytest.UsageError(
                "planning boundary and retained execution tests must be separate"
            )
