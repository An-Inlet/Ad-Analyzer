"""One explicit missing historical fixture asset; no application/runtime replacement."""

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from starlette.responses import Response

PIN = "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
NODES = frozenset({
    "tests/test_v2_execution_browser.py::test_v2_execution_review_browser[sqlite-False]",
    "tests/test_v2_execution_browser.py::test_v2_execution_review_browser[postgres-False]",
})
ASSET = "app/portal/static/reported-rule-view.mjs"
ASSET_DIGEST = "5c9b6722b2717c9f38afc347ff9cd1b0b03fa50397ddd89e9588e3262f4e72a2"


@pytest.fixture(autouse=True)
def exact_missing_historical_asset(request: pytest.FixtureRequest) -> Iterator[None]:
    if request.node.nodeid not in NODES:
        yield
        return
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == PIN
    content = Path(ASSET).read_bytes()
    assert hashlib.sha256(content).hexdigest() == ASSET_DIGEST
    client = request.getfixturevalue("replicas")[0]
    application = client.app
    path = "/app/assets/reported-rule-view.mjs"
    assert not any(getattr(route, "path", None) == path for route in application.routes)

    async def asset() -> Response:
        return Response(content, media_type="text/javascript")

    application.add_api_route(path, asset, methods=["GET"], include_in_schema=False)
    route = application.routes[-1]
    try:
        yield
    finally:
        application.router.routes.remove(route)
