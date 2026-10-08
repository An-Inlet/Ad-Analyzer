"""Pinned historical regressions in a separate interpreter; never current capabilities."""

import os
import signal
import subprocess
import tarfile
import time
from pathlib import Path

PIN = "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
TREES = {"app": "6507ee4da861c63ebbc9ce0210c558c0de19d873",
         "tests": "06cc6a9ecb7466c3e94a5bd6558ea73befbbe4cc"}
MAX_LOG_BYTES = 16 * 1024 * 1024
TIMEOUT_SECONDS = 1800


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments], text=True, timeout=30
    ).strip()


def extract(root: Path, destination: Path) -> None:
    """Only local, pinned ancestor objects; no fetch, checkout or shared DB mutation."""
    if git(root, "rev-parse", PIN + "^{commit}") != PIN:
        raise AssertionError("Missing exact historical commit")
    subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", PIN, "HEAD"],
        check=True, timeout=30,
    )
    for name, expected in TREES.items():
        if git(root, "rev-parse", PIN + ":" + name) != expected:
            raise AssertionError("Historical source tree changed")
    destination.mkdir()
    archive = destination.parent / "historical-source.tar"
    with archive.open("wb") as stream:
        subprocess.run(
            ["git", "-C", str(root), "archive", "--format=tar", PIN],
            stdout=stream, check=True, timeout=60,
        )
    with tarfile.open(archive) as source:
        source.extractall(destination, filter="data")
    archive.unlink()


def run_bounded(command: list[str], cwd: Path, env: dict[str, str], log: Path,
                timeout: int = TIMEOUT_SECONDS) -> int:
    with log.open("wb") as output:
        process = subprocess.Popen(
            command, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        started = time.monotonic()
        try:
            while process.poll() is None:
                if time.monotonic() - started > timeout or log.stat().st_size > MAX_LOG_BYTES:
                    raise AssertionError("Historical subprocess exceeded time/output bound")
                time.sleep(0.1)
            return process.returncode
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
