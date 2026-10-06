#!/usr/bin/env python3
"""Select an installed browser only after real synthetic H.264/AAC blob decoding.

No provider/network data: generated clips and a loopback-only HTTP fixture. The
selected executable is exported to all browser tests, not silently skipped.
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

CANDIDATES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
HTML = b"""<!doctype html><script>
const results=[]; let reported=false;
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


def probe(browser: str, clips: dict[str, bytes], directory: Path) -> list[dict[str, Any]]:
    complete = threading.Event()
    results: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def do_GET(self) -> None:
            data = clips.get(self.path, HTML)
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4" if self.path in clips else "text/html")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
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
    process = subprocess.Popen(
        [
            browser,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-background-networking",
            "--no-first-run",
            "--disable-extensions",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            f"--user-data-dir={directory}",
            f"http://127.0.0.1:{server.server_port}/",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not complete.wait(12):
            return [{"event": "browser_no_result"}]
        return results
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
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
