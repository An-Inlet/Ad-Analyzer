"""Opt-in loopback-only rendered PNG capture; no network or auth tracing."""

import base64
import json
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from websockets.sync.client import connect


def capture_saved_basis(profile: Path, output: Path) -> None:
    port = int((profile / "DevToolsActivePort").read_text().splitlines()[0])
    assert 0 < port < 65536
    with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}/json", timeout=5) as result:
        targets = json.load(result)
    pages = [item for item in targets if item.get("type") == "page"]
    assert len(pages) == 1
    websocket = pages[0]["webSocketDebuggerUrl"]
    assert websocket.startswith(f"ws://127.0.0.1:{port}/devtools/page/")
    with connect(websocket, open_timeout=5, max_size=16 * 1024 * 1024) as client:
        client.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Page.captureScreenshot",
                    "params": {
                        "format": "png",
                        "captureBeyondViewport": False,
                    },
                }
            )
        )
        message = json.loads(client.recv(timeout=10))
        assert message.get("id") == 1 and "error" not in message
        png = base64.b64decode(message["result"]["data"], validate=True)
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        output.write_bytes(png)
