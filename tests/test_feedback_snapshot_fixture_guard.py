"""Closed child SQLite target is checked before engine creation or source work."""

import sys
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures.retired_execution import candidate_receipt_seed_driver as child
from tests.retired_snapshot import PIN


@pytest.mark.parametrize("invalid", ["foreign", "query", "missing", "directory", "symlink"])
def test_child_rejects_unowned_sqlite_before_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("INLET_RETIRED_EXECUTION_CHILD", PIN)
    monkeypatch.setenv("PYTHONPATH", str(root))
    database = tmp_path / "current.sqlite"
    target = f"sqlite:///{database}"
    if invalid == "directory":
        database.mkdir()
    elif invalid != "missing":
        database.touch()
    if invalid == "foreign":
        foreign = tmp_path / "foreign.sqlite"
        foreign.touch()
        target = f"sqlite:///{foreign}"
    elif invalid == "query":
        target += "?mode=ro"
    elif invalid == "symlink":
        alias = tmp_path / "alias.sqlite"
        alias.symlink_to(database)
        target = f"sqlite:///{alias}"
    invoked: list[bool] = []

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        invoked.append(True)
        raise AssertionError("invalid target reached engine creation")

    monkeypatch.setattr(child, "create_engine", forbidden)
    monkeypatch.setattr(sys, "argv", ["driver", target, str(tmp_path / "ids.json")])
    with pytest.raises(AssertionError):
        child.main()
    assert invoked == []
    assert not (tmp_path / "ids.json").exists()
