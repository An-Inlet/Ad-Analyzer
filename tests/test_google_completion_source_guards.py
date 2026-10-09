"""Reject unsafe source-file shapes before opening a database or extracting source."""

import os
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL

from tests import google_completion_retained_fixture as parent
from tests.fixtures.retired_execution import google_completion_seed_driver as child


@pytest.mark.parametrize("side", [parent, child], ids=["parent", "child"])
@pytest.mark.parametrize(
    "shape",
    ["driver", "query", "username", "password", "host", "port", "memory", "relative", "other"],
)
def test_sqlite_target_rejects_nonowned_url(side: Any, shape: str, tmp_path: Path) -> None:
    expected = tmp_path / "current.sqlite"
    expected.touch()
    values: dict[str, Any] = dict(drivername="sqlite", database=str(expected))
    if shape == "driver":
        values["drivername"] = "sqlite+pysqlite"
    elif shape == "query":
        values["query"] = {"mode": "ro"}
    elif shape in {"username", "password", "host"}:
        values[shape] = "unowned"
        if shape == "password":
            values["username"] = "offline"
    elif shape == "port":
        values["port"] = 1
    else:
        values["database"] = {
            "memory": ":memory:",
            "relative": "current.sqlite",
            "other": str(tmp_path / "other.sqlite"),
        }[shape]
    with pytest.raises(AssertionError):
        side.owned_sqlite_target(
            URL.create(**values).render_as_string(hide_password=False), expected
        )
    assert expected.read_bytes() == b""


@pytest.mark.parametrize("side", [parent, child], ids=["parent", "child"])
@pytest.mark.parametrize(
    "shape", ["file_link", "ancestor_link", "directory", "fifo", "missing", "dotdot"]
)
def test_sqlite_target_rejects_nonregular_paths(side: Any, shape: str, tmp_path: Path) -> None:
    directory = tmp_path / "owned"
    directory.mkdir()
    expected = directory / "current.sqlite"
    if shape == "file_link":
        actual = tmp_path / "actual.sqlite"
        actual.write_bytes(b"untouched")
        expected.symlink_to(actual)
    elif shape == "ancestor_link":
        expected.touch()
        alias = tmp_path / "alias"
        alias.symlink_to(directory, target_is_directory=True)
        expected = alias / "current.sqlite"
    elif shape == "directory":
        expected.mkdir()
    elif shape == "fifo":
        os.mkfifo(expected)
    elif shape == "dotdot":
        expected.touch()
        expected = directory / ".." / "owned" / "current.sqlite"
    with pytest.raises((AssertionError, FileNotFoundError)):
        side.owned_sqlite_target(f"sqlite:///{expected}", expected)


@pytest.mark.parametrize("side", [parent, child], ids=["parent", "child"])
def test_sqlite_target_accepts_only_exact_owned_regular_file(side: Any, tmp_path: Path) -> None:
    expected = tmp_path / "current.sqlite"
    expected.touch()
    target = f"sqlite:///{expected}"
    assert side.owned_sqlite_target(target, expected) == target


def test_parent_rejects_alias_before_factory_or_ddl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    engine = create_engine("sqlite://")

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("database factory must not run")

    monkeypatch.setattr(parent, "create_engine", forbidden)
    try:
        with (
            pytest.raises(AssertionError),
            parent.retained_google_completion(engine, alias / "new", purpose="reader"),
        ):
            pytest.fail("unsafe source accepted")
        assert list(real.iterdir()) == []
    finally:
        engine.dispose()


def test_parent_uses_exclusive_file_creation_before_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts = tmp_path / "source"
    artifacts.mkdir()
    database = artifacts / "current.sqlite"
    database.write_bytes(b"must survive")
    # Existing artifact directories are rejected before touching their existing file.
    with (
        pytest.raises(FileExistsError),
        parent.retained_google_completion(cast(Engine, object()), artifacts, purpose="reader"),
    ):
        pytest.fail("existing source accepted")
    assert database.read_bytes() == b"must survive"
