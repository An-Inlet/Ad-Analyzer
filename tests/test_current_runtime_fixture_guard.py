"""Unsafe database names fail before any connection or retained child launch."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy import Engine
from sqlalchemy.engine import make_url

from tests.retired_snapshot import PIN


@pytest.mark.parametrize("kind", ["tiktok", "optimization"])
@pytest.mark.parametrize("entry", ["parent", "child"])
def test_production_named_database_rejected_before_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: str,
    kind: str,
) -> None:
    parent = importlib.import_module(
        "tests."
        + (
            "tiktok_draft_retained_fixture"
            if kind == "tiktok"
            else "optimization_source_retained_fixture"
        )
    )
    child = importlib.import_module(
        "tests.fixtures.retired_execution."
        + ("tiktok_draft_seed_driver" if kind == "tiktok" else "optimization_source_seed_driver")
    )
    root = Path(__file__).resolve().parents[1]
    url = "postgresql+psycopg://postgres@127.0.0.1:55432/inlet_prod_ci"
    monkeypatch.setenv("AD_ANALYZER_TEST_POSTGRES_URL", url)
    monkeypatch.setenv("AD_ANALYZER_CI_DISPOSABLE_POSTGRES", "true")
    monkeypatch.setenv("INLET_RETIRED_EXECUTION_CHILD", PIN)
    monkeypatch.setenv("PYTHONPATH", str(root))
    invoked: list[bool] = []

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        invoked.append(True)
        raise AssertionError("unsafe database must not connect or launch")

    monkeypatch.setattr(parent, "extract", forbidden)
    monkeypatch.setattr(parent, "run_bounded", forbidden)
    monkeypatch.setattr(child, "create_engine", forbidden)
    engine = cast(
        Engine,
        SimpleNamespace(
            dialect=SimpleNamespace(name="postgresql"),
            url=make_url(url),
            connect=forbidden,
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "driver",
            "inlet_test_" + "a" * 32,
            str(tmp_path / "ids.json"),
        ],
    )
    with pytest.raises(SystemExit) as failure:
        if entry == "parent":
            context = (
                parent.retained_tiktok_draft_fixture(engine, tmp_path / "fixture", b"unused")
                if kind == "tiktok"
                else parent.retained_optimization_source_fixture(engine, tmp_path / "fixture")
            )
            with context:
                raise AssertionError("unsafe fixture yielded")
        else:
            child.main()
    assert failure.value.code == 1 and invoked == []
    assert not (tmp_path / "ids.json").exists()
