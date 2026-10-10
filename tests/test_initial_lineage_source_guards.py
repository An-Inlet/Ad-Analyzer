"""Closed scalar/storage contracts reject before any original producer starts."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine

from tests.fixtures.retired_execution.initial_lineage_seed_driver import (
    owned_sqlite_target as child_sqlite,
)
from tests.initial_lineage_retained_fixture import (
    InitialLineageIds,
    artifact_path,
    decode_ids,
    retained_initial_lineage,
)
from tests.social_producer_retained_fixture import owned_sqlite_target


def payload() -> dict[str, Any]:
    return asdict(
        InitialLineageIds(
            "creation",
            "meta_ads",
            1,
            2,
            "a" * 32,
            "b" * 32,
            "c" * 32,
            "d" * 32,
            None,
            None,
            "1",
            "e" * 64,
            "f" * 64,
            5,
            0,
        )
    )


@pytest.mark.parametrize(
    "change",
    [
        "bool_workspace",
        "bool_account",
        "bool_posts",
        "wrong_mode",
        "provider",
        "extra",
        "missing",
        "parent",
        "id",
        "oversize",
        "array",
    ],
)
def test_closed_scalar_payload(tmp_path: Path, change: str) -> None:
    raw: Any = payload()
    if change == "bool_workspace":
        raw["workspace_id"] = True
    elif change == "bool_account":
        raw["account_id"] = True
    elif change == "bool_posts":
        raw["activation_posts"] = False
    elif change == "wrong_mode":
        raw["mode"] = "activation"
    elif change == "provider":
        raw["provider"] = "google_ads"
    elif change == "extra":
        raw["authority"] = True
    elif change == "missing":
        del raw["reservation_id"]
    elif change == "parent":
        raw["parent_run_id"] = "a" * 32
    elif change == "id":
        raw["run_id"] = "foreign"
    elif change == "oversize":
        raw["run_id"] = "a" * 4097
    else:
        raw = []
    output = tmp_path / "ids.json"
    output.write_text(json.dumps(raw))
    with pytest.raises(AssertionError):
        decode_ids(output, "creation")


@pytest.mark.parametrize("mode", ["creation", "activation"])
def test_exact_scalar_payload(tmp_path: Path, mode: str) -> None:
    raw = payload()
    if mode == "activation":
        raw.update(mode=mode, parent_run_id="1" * 32, parent_review_id="2" * 32, activation_posts=3)
    output = tmp_path / "ids.json"
    output.write_text(json.dumps(raw))
    assert decode_ids(output, mode).mode == mode


@pytest.mark.parametrize("guard", [owned_sqlite_target, child_sqlite])
@pytest.mark.parametrize("change", ["query", "foreign", "alias"])
def test_sqlite_owned_path(tmp_path: Path, guard: Any, change: str) -> None:
    owned = tmp_path / "current.sqlite"
    owned.touch()
    foreign = tmp_path / "foreign.sqlite"
    foreign.touch()
    alias = tmp_path / "alias.sqlite"
    alias.symlink_to(owned)
    target = f"sqlite:///{owned}"
    if change == "query":
        target += "?mode=ro"
    elif change == "foreign":
        target = f"sqlite:///{foreign}"
    else:
        target = f"sqlite:///{alias}"
    with pytest.raises(AssertionError):
        guard(target, owned)


def test_artifact_alias_and_mode_reject_before_setup(tmp_path: Path) -> None:
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(AssertionError):
        artifact_path(alias / "new")
    assert not (tmp_path / "new").exists()
    engine = create_engine("sqlite://")
    try:
        with (
            pytest.raises(AssertionError),
            retained_initial_lineage(
                engine,
                tmp_path / "not-created",
                "other",  # type: ignore[arg-type]
            ),
        ):
            pytest.fail("unknown mode yielded")
        assert not (tmp_path / "not-created").exists()
    finally:
        engine.dispose()
