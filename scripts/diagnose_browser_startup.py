"""Bounded startup evidence only; never select or codec-qualify a browser.

Run from the checkout root: python -m scripts.diagnose_browser_startup
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from scripts.check_browser_media import probe

FAMILIES = (("google-chrome", "google-chrome-stable"), ("chromium", "chromium-browser"))


def observations() -> dict[str, Any]:
    result: dict[str, Any] = {
        "system": platform.system()[:80],
        "kernel": platform.release()[:160],
        "cpu_count": os.cpu_count(),
    }
    try:
        result["shared_memory_bytes"] = shutil.disk_usage("/dev/shm").total
    except OSError:
        result["shared_memory_bytes"] = None
    try:
        with Path("/etc/os-release").open() as source:
            lines = source.read(4096).splitlines()
        result["os"] = {
            key: value.strip('"')[:120]
            for line in lines if "=" in line
            for key, value in [line.split("=", 1)]
            if key in {"ID", "VERSION_ID"}
        }
    except OSError:
        result["os"] = None
    return result


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps({"kind": "environment", "observations": observations(),
                      "codec_qualification": "not_attempted"}), flush=True)
    seen: set[str] = set()
    count = 0
    with tempfile.TemporaryDirectory(prefix="inlet-startup-", dir="/tmp") as temporary:
        for family in FAMILIES:
            browser = next((path for name in family if (path := shutil.which(name))), None)
            if browser is None or os.path.realpath(browser) in seen:
                continue
            seen.add(os.path.realpath(browser))
            count += 1
            try:
                version = subprocess.run(
                    [browser, "--version"], capture_output=True, text=True,
                    check=True, timeout=5,
                ).stdout.strip()[:200]
            except (OSError, subprocess.SubprocessError):
                version = "unavailable"
            try:
                # Deliberately invalid bodies: this observes startup, not decoding.
                result = probe(browser, {"/silent": b"", "/aac": b""},
                               Path(temporary) / f"browser-{count}")
            except OSError:
                result = [{"event": "browser_launch_unavailable"}]
            print(json.dumps({"kind": "startup_observation", "browser": Path(browser).name,
                              "version": version, "result": result,
                              "codec_qualification": "not_attempted"}), flush=True)
    print(json.dumps({"kind": "collection_complete", "browser_count": count,
                      "codec_qualification": "not_attempted"}), flush=True)
    return 0 if count else 2


if __name__ == "__main__":
    raise SystemExit(main())
