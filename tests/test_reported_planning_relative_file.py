"""Both relative producer entry points reject unowned SQLite files before DB access."""

import sys
from pathlib import Path
from typing import Any

import app
import pytest
from sqlalchemy import create_engine

from tests import reported_planning_relative_fixture as parent
from tests.fixtures.retired_execution import reported_planning_relative_seed_driver as child
from tests.reported_planning_original_fixture import ExpectedPlanningConfirmation
from tests.retired_snapshot import PIN


@pytest.mark.parametrize("site", ["parent", "child"])
@pytest.mark.parametrize("mode", ["foreign", "query", "missing", "symlink", "driver"])
def test_owned_sqlite_boundary_rejects_before_database_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, site: str, mode: str
) -> None:
    owned = tmp_path / "current.sqlite"
    foreign = tmp_path / "foreign.sqlite"
    foreign.write_bytes(b"foreign sentinel")
    if mode == "symlink":
        owned.symlink_to(foreign)
    elif mode != "missing":
        owned.write_bytes(b"owned sentinel")
    target = f"sqlite:///{foreign if mode == 'foreign' else owned}"
    if mode == "query":
        target += "?mode=ro"
    elif mode == "driver":
        target = target.replace("sqlite:", "sqlite+pysqlite:")
    artifacts = tmp_path / "original"

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("database access or producer launch before ownership check")

    if site == "parent":
        engine = create_engine(target)
        monkeypatch.setattr(parent, "effect_graph", forbidden)
        monkeypatch.setattr(parent, "run_bounded", forbidden)
        try:
            with (
                pytest.raises(AssertionError),
                parent.retained_reported_planning_relative_fixture(
                    engine, artifacts, expectation=ExpectedPlanningConfirmation()
                ),
            ):
                pytest.fail("invalid owned file yielded")
        finally:
            engine.dispose()
    else:
        monkeypatch.setattr(sys, "argv", ["closed-driver", target, str(artifacts / "ids.json")])
        monkeypatch.setenv("INLET_RETIRED_EXECUTION_CHILD", PIN)
        assert app.__file__ is not None
        monkeypatch.setenv("PYTHONPATH", str(Path(app.__file__).resolve().parent.parent))
        monkeypatch.setattr(child, "create_engine", forbidden)
        with pytest.raises(AssertionError):
            child.main()
    assert foreign.read_bytes() == b"foreign sentinel"
    assert not (artifacts / "ids.json").exists()
    if mode == "missing":
        assert not owned.exists()
    elif mode != "symlink":
        assert owned.read_bytes() == b"owned sentinel"


@pytest.mark.parametrize("site", ["parent", "child"])
def test_exact_owned_existing_plain_file_is_accepted(tmp_path: Path, site: str) -> None:
    owned = tmp_path / "current.sqlite"
    owned.write_bytes(b"not opened by pure guard")
    target = f"sqlite:///{owned}"
    guard = parent.owned_sqlite_target if site == "parent" else child.owned_sqlite_target
    assert guard(target, owned) == target
