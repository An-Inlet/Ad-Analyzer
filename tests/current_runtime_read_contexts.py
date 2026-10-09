"""Per-function owned current contexts; no retained execution capability override."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import Engine

from tests.optimization_source_retained_fixture import retained_optimization_source_fixture
from tests.test_customer_identity import replicas
from tests.tiktok_draft_retained_fixture import retained_tiktok_draft_fixture


@pytest.fixture()
def current_tiktok_source(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    encoded: Any,
) -> Iterator[Any]:
    with retained_tiktok_draft_fixture(customer_engine, tmp_path / "retained", encoded()) as (
        engine,
        ids,
        media,
    ):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        try:
            yield engine, media, clients, ids
        finally:
            clients[0].close()
            clients[1].close()


@pytest.fixture()
def current_optimization_source(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Any]:
    with retained_optimization_source_fixture(customer_engine, tmp_path / "retained") as (
        engine,
        ids,
        media,
    ):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        try:
            yield engine, media, clients, ids
        finally:
            clients[0].close()
            clients[1].close()
