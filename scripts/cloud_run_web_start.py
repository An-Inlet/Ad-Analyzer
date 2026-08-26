"""Run the reversible database migration before starting the single web process."""

from __future__ import annotations

import os
import subprocess


def main() -> None:
    port = os.environ.get("PORT", "8000")
    if not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
        raise SystemExit("PORT must be a valid TCP port.")
    subprocess.run(
        ["python", "scripts/validate_deployment_startup.py", "--process", "migration"],
        check=True,
    )
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    subprocess.run(
        ["python", "scripts/validate_deployment_startup.py", "--process", "web"],
        check=True,
    )
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
            "--proxy-headers",
        ],
    )


if __name__ == "__main__":
    main()
