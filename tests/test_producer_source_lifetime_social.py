"""Actual parent DDL sees source retained across the historical child handshake."""

import json
from pathlib import Path

import pytest


def test_source_survives_parent_ddl_then_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alembic import command
    from alembic.config import Config

    from tests.test_social_configuration_migration import test_populated_no_dsa_review_roundtrip

    upgrade = command.upgrade
    observed = []
    source = tmp_path / "retained-social/source"

    def checked(config: Config, revision: str, *args: object, **kwargs: object) -> None:
        if revision == "20261006_0059":
            observed.append(source.exists())
        upgrade(config, revision, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(command, "upgrade", checked)
    test_populated_no_dsa_review_roundtrip(monkeypatch, tmp_path)
    assert observed == [True, False]
    assert not source.exists()
    artifact = source.parent
    assert all(
        (artifact / name).is_file()
        for name in ("producer.log", "prepared.json", "confirmed.json", "continue.json")
    )
    record = json.loads((artifact / "source-lifetime.json").read_text())
    assert record["state"] == "removed" and record["completion"] == "success"


def test_source_removed_after_actual_forced_phase_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_social_restore_producer_boundary import (
        test_actual_parent_schema_cleanup_after_child_deadline,
    )

    test_actual_parent_schema_cleanup_after_child_deadline(tmp_path, monkeypatch)
    artifact = tmp_path / "retained-social"
    assert not (artifact / "source").exists()
    assert (artifact / "prepared.json").is_file() and (artifact / "producer.log").is_file()
    record = json.loads((artifact / "source-lifetime.json").read_text())
    assert record["state"] == "removed" and record["completion"] == "nonzero_reaped"
