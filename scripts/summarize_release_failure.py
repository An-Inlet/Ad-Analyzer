"""Emit only allowlisted failure categories from private Cloud Run log exports."""

import json
import re
import sys
from pathlib import Path

CATEGORIES = (
    "ModuleNotFoundError",
    "ImportError",
    "PermissionDenied",
    "PermissionError",
    "OperationalError",
    "ProgrammingError",
    "IntegrityError",
    "DuplicateTable",
    "UndefinedTable",
    "UndefinedColumn",
    "InvalidPassword",
    "ValidationError",
    "Can't locate revision",
    "Permission denied",
    "permission denied",
)


def summarize(entries: list[dict]) -> list[str]:
    found = set()
    for entry in entries:
        message = str(entry.get("textPayload", "")) + str(
            entry.get("jsonPayload", {}).get("message", "")
        )
        for category in CATEGORIES:
            if category in message:
                found.add(category)
        for check in ("database_url", "required_secrets", "write_guards", "production_allowlists"):
            if re.search(rf"\b{check}: failed\b", message):
                found.add(f"{check}: failed")
    return sorted(found) or [
        "No allowlisted error category found; private logs need operator review."
    ]


if __name__ == "__main__":
    print("\n".join(summarize(json.loads(Path(sys.argv[1]).read_text()))))
