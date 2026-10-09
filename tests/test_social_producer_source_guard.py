"""New TikTok producer rejects unowned files before opening a database."""

import sys
from pathlib import Path
from typing import Any

import app
import pytest
from sqlalchemy import create_engine

from tests import social_producer_retained_fixture as parent
from tests.fixtures.retired_execution import social_producer_seed_driver as child
from tests.retired_snapshot import PIN


@pytest.mark.parametrize("site", ["parent", "child"])
@pytest.mark.parametrize("mode", ["foreign", "query", "missing", "symlink", "driver"])
def test_social_source_owned_file_guard(tmp_path: Path, site: str, mode: str) -> None:
    owned, foreign = tmp_path / "current.sqlite", tmp_path / "foreign.sqlite"
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
    guard = parent.owned_sqlite_target if site == "parent" else child.owned_sqlite_target
    with pytest.raises(AssertionError):
        guard(target, owned)
    assert foreign.read_bytes() == b"foreign sentinel"


@pytest.mark.parametrize("site", ["parent", "child"])
def test_social_source_exact_owned_file(tmp_path: Path, site: str) -> None:
    owned = tmp_path / "current.sqlite"
    owned.write_bytes(b"not opened")
    target = f"sqlite:///{owned}"
    guard = parent.owned_sqlite_target if site == "parent" else child.owned_sqlite_target
    assert guard(target, owned) == target


def test_social_parent_rejects_symlink_ancestor_before_file_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    link = tmp_path / "link"
    link.symlink_to(foreign, target_is_directory=True)
    engine = create_engine("sqlite://")

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("database construction before owned path validation")

    monkeypatch.setattr(parent, "create_engine", forbidden)
    try:
        with pytest.raises(AssertionError), parent.retained_social_producer(
            engine, link / "artifacts", "meta_ads", None, None
        ):
            pytest.fail("invalid path yielded")
    finally:
        engine.dispose()
    assert list(foreign.iterdir()) == []


@pytest.mark.parametrize("mode", ["foreign", "query", "symlink", "driver"])
def test_social_child_rejects_before_database_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    owned = tmp_path / "current.sqlite"
    foreign = tmp_path / "foreign.sqlite"
    foreign.write_bytes(b"foreign sentinel")
    if mode == "symlink":
        owned.symlink_to(foreign)
    else:
        owned.write_bytes(b"owned sentinel")
    target = f"sqlite:///{foreign if mode == 'foreign' else owned}"
    if mode == "query":
        target += "?mode=ro"
    elif mode == "driver":
        target = target.replace("sqlite:", "sqlite+pysqlite:")
    monkeypatch.setattr(sys, "argv", ["driver", target, str(tmp_path / "ids.json"), "meta_ads"])
    monkeypatch.setenv("INLET_RETIRED_EXECUTION_CHILD", PIN)
    assert app.__file__ is not None
    monkeypatch.setenv("PYTHONPATH", str(Path(app.__file__).resolve().parent.parent))

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("database factory called before owned file guard")

    monkeypatch.setattr(child, "create_engine", forbidden)
    with pytest.raises(AssertionError):
        child.main()
    assert foreign.read_bytes() == b"foreign sentinel"
    assert not (tmp_path / "ids.json").exists()
