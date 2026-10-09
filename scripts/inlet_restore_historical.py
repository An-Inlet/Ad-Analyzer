"""Closed genuine synthetic producer for the default disposable restore drill."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import tarfile
import time
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, MetaData, Table, inspect, make_url, select, text

from .inlet_producer_source_lifetime import SourceLifetime
from .inlet_restore_bootstrap import expected_bootstrap
from .reset_disposable_postgres import validate_disposable_url

PIN = "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
TREES = {
    "app": "6507ee4da861c63ebbc9ce0210c558c0de19d873",
    "tests": "06cc6a9ecb7466c3e94a5bd6558ea73befbbe4cc",
    "scripts": "c49d7769faa20df001536e6f819a1e1f7c860c57",
}
ROOT = Path(__file__).resolve().parents[1]
Mode = Literal["native", "fixture"]
MAX_LOG_BYTES = 16 * 1024 * 1024


class HistoricalSeedError(RuntimeError):
    """Fixed safe diagnostic, never raw database/source/process output."""


def require(
    condition: bool, reason: str = "synthetic historical seed boundary unavailable"
) -> None:
    if not condition:
        raise HistoricalSeedError(reason)


@dataclass(frozen=True)
class RetainedRestoreIds:
    workspace_ids: tuple[int, int]
    replacement_ids: tuple[str, ...]
    attempt_ids: tuple[str, ...]
    held_reservation_ids: tuple[str, ...]
    social_approval_ids: tuple[str, ...]


def _heads() -> set[str]:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return set(ScriptDirectory.from_config(config).get_heads())


def guard(engine: Engine, mode: Mode) -> dict[str, list[dict[str, Any]]]:
    require(mode in {"native", "fixture"})
    if engine.dialect.name == "postgresql":
        url = make_url(validate_disposable_url())
        require(url.host in {"localhost", "127.0.0.1", "::1"} and not url.query)
        require(engine.url.set(query={}) == url)
        with engine.connect() as db:
            schema = str(db.scalar(text("SELECT current_schema()")))
            prefix = "inlet_restore_" if mode == "native" else "inlet_test_"
            require(re.fullmatch(prefix + r"[a-f0-9]{32}", schema) is not None)
            require(
                dict(engine.url.query) == {"options": f"-csearch_path={schema}"}
                or (mode == "fixture" and not engine.url.query)
            )
            if mode == "native":
                require(
                    set(db.scalars(text("SELECT version_num FROM alembic_version"))) == _heads()
                )
    else:
        require(mode == "fixture" and engine.dialect.name == "sqlite")
        path = Path(engine.url.database or "").resolve()
        require(
            path.name == "current.sqlite"
            and re.fullmatch(r"inlet_restore_fixture_[a-f0-9]{32}", path.parent.name) is not None
        )
        require(path.is_file() and engine.url.database == str(path))
    expected = expected_bootstrap() if mode == "native" else {}
    snapshot: dict[str, list[dict[str, Any]]] = {}
    tables = set(inspect(engine).get_table_names())
    require(set(expected) <= tables)
    with engine.connect() as db:
        for name in sorted(tables - {"alembic_version"}):
            if name not in expected:
                quoted = db.dialect.identifier_preparer.quote(name)
                require(db.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0)
                continue
            table = Table(name, MetaData(), autoload_with=db, resolve_fks=False)
            rows = [dict(row) for row in db.execute(select(table)).mappings()]
            stripped = [
                {k: v for k, v in row.items() if k not in {"created_at", "updated_at"}}
                for row in rows
            ]

            def key(value: dict[str, Any]) -> str:
                return json.dumps(value, sort_keys=True, default=str)

            require(
                sorted(map(key, stripped)) == sorted(map(key, expected.get(name, []))),
                "synthetic migration bootstrap mismatch",
            )
            if rows:
                snapshot[name] = rows
    return snapshot


def unchanged_bootstrap(engine: Engine, snapshot: dict[str, list[dict[str, Any]]]) -> None:
    with engine.connect() as db:
        for name, rows in snapshot.items():
            table = Table(name, MetaData(), autoload_with=db, resolve_fks=False)
            keys = list(table.primary_key.columns)
            for before in rows:
                statement = select(table).where(*(column == before[column.name] for column in keys))
                require(
                    json.dumps(
                        dict(db.execute(statement).mappings().one()), sort_keys=True, default=str
                    )
                    == json.dumps(before, sort_keys=True, default=str)
                )


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], text=True, stderr=subprocess.DEVNULL, timeout=30
    ).strip()


def extract(destination: Path) -> None:
    require(_git("rev-parse", PIN + "^{commit}") == PIN)
    subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", PIN, "HEAD"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    for name, tree in TREES.items():
        require(_git("rev-parse", PIN + ":" + name) == tree)
    destination.mkdir()
    archive = destination.parent / "source.tar"
    with archive.open("wb") as stream:
        subprocess.run(
            ["git", "-C", str(ROOT), "archive", "--format=tar", PIN],
            stdout=stream,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=60,
        )
    with tarfile.open(archive) as source:
        source.extractall(destination, filter="data")
    archive.unlink()


def _run(args: list[str], source: Path, env: dict[str, str], log: Path) -> None:
    with log.open("wb") as output:
        process = subprocess.Popen(
            args,
            cwd=source,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        started = time.monotonic()
        try:
            while process.poll() is None:
                require(time.monotonic() - started <= 180 and log.stat().st_size <= MAX_LOG_BYTES)
                time.sleep(0.1)
            require(log.stat().st_size <= MAX_LOG_BYTES)
            if process.returncode != 0:
                stages = {"guard", "producer", "bootstrap", "lineage", "output"}
                last = next(
                    (
                        line[6:]
                        for line in reversed(log.read_text().splitlines())
                        if line.startswith("STAGE=") and line[6:] in stages
                    ),
                    "unknown",
                )
                raise HistoricalSeedError("synthetic historical child failed at " + last)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)


def read_ids(engine: Engine) -> RetainedRestoreIds:
    with engine.connect() as db:
        rows = db.execute(text("SELECT id FROM workspaces WHERE id IN (901,902) ORDER BY id"))
        workspace_ids = tuple(row[0] for row in rows)
        require(workspace_ids == (901, 902))

        def ids(table: str, clause: str = "", column: str = "id") -> tuple[str, ...]:
            return tuple(
                db.scalars(text(f"SELECT {column} FROM {table} {clause} ORDER BY {column}"))
            )

        result = RetainedRestoreIds(
            (901, 902),
            ids("provider_reservation_replacements"),
            ids("provider_execution_attempts"),
            ids("provider_exposure_reservations", "WHERE state='held'"),
            ids("customer_social_configuration_approvals", column="review_id"),
        )
        require(
            len(result.replacement_ids)
            == len(result.held_reservation_ids)
            == len(result.social_approval_ids)
            == 1
            and len(result.attempt_ids) == 2
        )
        for table, workspace in (
            ("provider_reservation_replacements", 901),
            ("provider_execution_attempts", 901),
            ("provider_exposure_reservations", 901),
            ("customer_social_configuration_approvals", 902),
        ):
            require(set(db.scalars(text(f"SELECT workspace_id FROM {table}"))) == {workspace})
    return result


def _seed(engine: Engine, artifacts: Path, mode: Mode) -> RetainedRestoreIds:
    before = guard(engine, mode)
    tables = set(inspect(engine).get_table_names())
    artifacts.mkdir(parents=True, exist_ok=True)
    lifetime_context = (
        SourceLifetime.open("restore_fixture", artifacts) if mode == "fixture" else nullcontext()
    )
    with lifetime_context as lifetime:
        source = lifetime.source if lifetime else artifacts / "historical-source"
        extract(source)
        if lifetime:
            lifetime.extracted()
        if engine.dialect.name == "postgresql":
            with engine.connect() as db:
                target = str(db.scalar(text("SELECT current_schema()")))
        else:
            target = str(engine.url.database)
        output = artifacts / "seed-ids.json"
        require(not output.exists())
        if lifetime:
            lifetime.child_started()
        _run(
            [
                sys.executable,
                str(ROOT / "scripts/inlet_restore_seed_child.py"),
                mode,
                target,
                str(output),
            ],
            source,
            dict(os.environ, INLET_RESTORE_HISTORICAL_CHILD=PIN, PYTHONPATH=str(source)),
            artifacts / "producer.log",
        )
        if lifetime:
            lifetime.after_reaped(0)
    require(output.stat().st_size <= 16384)
    raw = json.loads(output.read_text())
    require(type(raw) is dict and set(raw) == set(RetainedRestoreIds.__dataclass_fields__))
    require(
        raw["workspace_ids"] == [901, 902]
        and all(type(value) is int for value in raw["workspace_ids"])
    )
    for name in set(raw) - {"workspace_ids"}:
        values = raw[name]
        require(
            type(values) is list
            and 0 < len(values) <= 64
            and all(type(value) is str and re.fullmatch(r"[a-f0-9]{32}", value) for value in values)
        )
        require(values == sorted(set(values)))
    result = read_ids(engine)
    require(raw == {name: list(getattr(result, name)) for name in raw})
    require(set(inspect(engine).get_table_names()) == tables)
    if mode == "native":
        with engine.connect() as db:
            require(set(db.scalars(text("SELECT version_num FROM alembic_version"))) == _heads())
    unchanged_bootstrap(engine, before)
    return result


def seed_retained_graph(engine: Engine, artifacts: Path) -> RetainedRestoreIds:
    try:
        return _seed(engine, artifacts, "native")
    except HistoricalSeedError:
        raise
    except Exception:
        raise HistoricalSeedError("synthetic historical seed failed") from None
