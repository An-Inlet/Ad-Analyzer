"""Bounded Chrome target readiness, separate from DevTools server readiness."""

import time
from collections.abc import Callable
from typing import Any
from urllib.error import URLError


def wait_for_page_target(
    targets: Callable[[], list[dict[str, Any]]],
    *,
    target_id: str | None = None,
    timeout: float = 10,
) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            current = targets()
        except (URLError, TimeoutError):
            current = []
        for target in current:
            websocket = target.get("webSocketDebuggerUrl")
            if (
                target.get("type") == "page"
                and isinstance(websocket, str)
                and websocket
                and (target_id is None or target.get("id") == target_id)
            ):
                return websocket
        time.sleep(0.03)
    raise AssertionError("Chromium did not expose a ready page target before the deadline")
