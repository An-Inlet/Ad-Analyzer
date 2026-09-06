"""Select existing application jobs by entrypoint and the web service's database."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def select_role(job: dict[str, Any], service: dict[str, Any]) -> str | None:
    """Reject unrelated jobs even if their resource names resemble the application."""
    web = service["spec"]["template"]["spec"]["containers"][0]
    containers = (
        job.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    if len(containers) != 1:
        return None
    container = containers[0]
    expected = {item["name"]: item.get("value") for item in web.get("env", [])}
    actual = {item["name"]: item.get("value") for item in container.get("env", [])}
    for key in ("CLOUD_SQL_CONNECTION_NAME", "DATABASE_NAME"):
        if not expected.get(key) or actual.get(key) != expected[key]:
            return None
    command = " ".join(container.get("command", []) + container.get("args", []))
    if "app.jobs.google_ads_sync_once" in command:
        return "sync"
    if "alembic upgrade head" in command:
        return "migration"
    return None


if __name__ == "__main__":
    import sys

    role = select_role(
        json.loads(Path(sys.argv[1]).read_text()), json.loads(Path(sys.argv[2]).read_text())
    )
    print(role or "unrelated")
