#!/usr/bin/env python3
"""Select an installed browser only after real synthetic H.264/AAC blob decoding.

No provider/network data: generated clips and a loopback-only HTTP fixture. The
selected executable is exported to all browser tests, not silently skipped.
"""

import argparse
import http.client
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from collections import deque
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

CANDIDATES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
HTML = b"""<!doctype html><script>
const results=[]; let reported=false;
window.onerror=()=>fetch('/diagnostic',{method:'POST',body:'javascript_error'});
window.onunhandledrejection=()=>fetch('/diagnostic',{method:'POST',body:'unhandled_rejection'});
function finish(){if(reported||results.length!==2)return;reported=true;
fetch('/result',{method:'POST',body:JSON.stringify(results)});}
for(const kind of ['silent','aac']){
const v=document.createElement('video');v.preload='auto';
document.documentElement.append(v);let done=false;
function result(event){if(done)return;done=true;results.push({kind,event,
h264:v.canPlayType('video/mp4; codecs="avc1.64000a"'),
aac:v.canPlayType('audio/mp4; codecs="mp4a.40.2"'),
readyState:v.readyState,width:v.videoWidth,
error:v.error?{code:v.error.code,message:v.error.message.slice(0,300)}:null});finish();}
v.onloadeddata=()=>result('loadeddata');v.onerror=()=>result('error');
fetch('/'+kind).then(r=>r.blob()).then(b=>{v.src=URL.createObjectURL(b);}).catch(()=>result('fetch_error'));
setTimeout(()=>result('timeout'),8000);
}
</script>"""


def startup_evidence(directory: Path, expected_url: str) -> dict[str, Any]:
    """Read only bounded local browser diagnostics; never a qualification signal."""
    result: dict[str, Any] = {"devtools_ready": False}
    try:
        with (directory / "DevToolsActivePort").open() as source:
            lines = source.read(512).splitlines()
        port = int(lines[0])
        if not 1 <= port <= 65535:
            return result
    except (OSError, ValueError, IndexError):
        return result
    result["devtools_ready"] = True
    for endpoint, label in (("/json/version", "version"), ("/json/list", "targets")):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.2)
        try:
            connection.request("GET", endpoint)
            response = connection.getresponse()
            body = response.read(8193)
            if response.status != 200 or len(body) > 8192:
                result[label] = "unavailable"
                continue
            value = json.loads(body)
            if label == "version":
                result[label] = "ready" if isinstance(value, dict) else "invalid"
            elif isinstance(value, list):
                result["page_targets"] = sum(
                    isinstance(item, dict) and item.get("type") == "page" for item in value
                )
                result["expected_navigation"] = any(
                    isinstance(item, dict) and item.get("url") == expected_url for item in value
                )
            else:
                result[label] = "invalid"
        except (OSError, ValueError, http.client.HTTPException):
            result[label] = "unavailable"
        finally:
            connection.close()
    return result


def stop_browser(process: subprocess.Popen[bytes]) -> None:
    """Stop the isolated browser group, including children after parent exit."""
    if os.name == "posix":
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    finally:
        if os.name == "posix":
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)


def probe(browser: str, clips: dict[str, bytes], directory: Path) -> list[dict[str, Any]]:
    started = time.monotonic()
    first_request: float | None = None
    complete = threading.Event()
    results: list[dict[str, Any]] = []
    requests: dict[str, int] = {}
    diagnostics: list[str] = []
    stderr: deque[str] = deque(maxlen=20)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def do_GET(self) -> None:
            nonlocal first_request
            if self.path == "/health":
                self.send_response(204)
                self.end_headers()
                return
            if first_request is None:
                first_request = time.monotonic() - started
            key = self.path if self.path in {"/", "/silent", "/aac"} else "other"
            requests[key] = requests.get(key, 0) + 1
            data = clips.get(self.path, HTML)
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4" if self.path in clips else "text/html")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            if self.path == "/diagnostic" and 0 < length <= 64:
                diagnostic = self.rfile.read(length).decode("ascii", errors="replace")
                if (
                    diagnostic in {"javascript_error", "unhandled_rejection"}
                    and len(diagnostics) < 4
                ):
                    diagnostics.append(diagnostic)
                self.send_response(200)
                self.end_headers()
                return
            if self.path != "/result" or not 0 < length <= 4096:
                self.send_error(400)
                return
            value = json.loads(self.rfile.read(length))
            if isinstance(value, list) and len(value) == 2:
                results.extend(value)
            self.send_response(200)
            self.end_headers()
            complete.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    expected_url = f"http://127.0.0.1:{server.server_port}/"
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=0.2)
    try:
        connection.request("GET", "/health")
        loopback_ready = connection.getresponse().status == 204
    except (OSError, http.client.HTTPException):
        loopback_ready = False
    finally:
        connection.close()
    process = subprocess.Popen(
        [
            browser,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-background-networking",
            "--no-first-run",
            "--disable-extensions",
            "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            f"--user-data-dir={directory}",
            expected_url,
        ],
        start_new_session=os.name == "posix",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env={
            key: os.environ[key]
            for key in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
            if key in os.environ
        },
    )

    def drain_stderr() -> None:
        assert process.stderr is not None
        while chunk := process.stderr.readline(1024):
            stderr.append(chunk.decode("utf-8", errors="replace").strip()[:1024])

    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    stderr_thread.start()
    try:
        deadline = time.monotonic() + 12
        while not complete.wait(0.1) and process.poll() is None and time.monotonic() < deadline:
            pass
        if not complete.is_set():
            return [
                {
                    "event": "browser_no_result",
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "first_request_seconds": first_request,
                    "loopback_ready": loopback_ready,
                    "startup": startup_evidence(directory, expected_url),
                    "exit_code": process.poll(),
                    "requests": dict(requests),
                    "javascript": diagnostics[:4],
                    "stderr": list(stderr),
                }
            ]
        return results
    finally:
        stop_browser(process)
        stderr_thread.join(timeout=2)
        if process.stderr is not None:
            process.stderr.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-env", type=Path)
    args = parser.parse_args()
    selected = None
    seen: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="inlet-codec-", dir="/tmp") as temporary:
        root = Path(temporary)
        clips = {}
        for kind in ("silent", "aac"):
            output = root / f"{kind}.mp4"
            command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=green:s=64x64:r=10"]
            if kind == "aac":
                command += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-c:a", "aac"]
            command += [
                "-t",
                "0.5",
                "-c:v",
                "libx264",
                "-threads",
                "1",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-y",
                str(output),
            ]
            subprocess.run(command, check=True, capture_output=True, timeout=30)
            clips["/" + kind] = output.read_bytes()
        for name in CANDIDATES:
            browser = shutil.which(name)
            if browser is None or os.path.realpath(browser) in seen:
                continue
            seen.add(os.path.realpath(browser))
            results = probe(browser, clips, root / (name + "-profile"))
            version = subprocess.run(
                [browser, "--version"], check=True, capture_output=True, text=True, timeout=10
            ).stdout.strip()
            print(json.dumps({"browser": name, "version": version, "decode": results}), flush=True)
            passed = (
                len(results) == 2
                and {r.get("kind") for r in results} == {"silent", "aac"}
                and all(
                    r.get("event") == "loadeddata"
                    and r.get("readyState", 0) >= 2
                    and r.get("width") == 64
                    and r.get("error") is None
                    for r in results
                )
            )
            if passed and selected is None:
                selected = browser
        if selected is None:
            raise SystemExit("No installed browser decoded both required H.264/AAC MP4 fixtures.")
    print("Selected codec-qualified browser: " + selected)
    if args.github_env:
        if any(c in selected for c in "\r\n"):
            raise SystemExit("Invalid browser path")
        with args.github_env.open("a") as output:
            output.write("INLET_TEST_BROWSER=" + selected + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
