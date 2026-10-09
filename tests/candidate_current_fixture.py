"""Deferred import avoids cycles in the original shared candidate fixture module."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Engine

if TYPE_CHECKING:
    from tests.candidate_read_retained_fixture import CandidateReadIds


@pytest.fixture
def current_candidate_read(
    customer_engine: Engine,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> Iterator[tuple[Engine, "CandidateReadIds"]]:
    from tests.candidate_read_retained_fixture import retained_candidate_read_fixture

    provider = request.node.callspec.params.get("provider", "google_ads")
    with retained_candidate_read_fixture(
        customer_engine, tmp_path / "current-candidate-source", provider
    ) as value:
        yield value
