"""Bounded per-test evidence for nested validation failures, not only a stdout tail."""

from pathlib import Path
from xml.etree import ElementTree

# Parameterized boundary-test IDs alone exceed 16 MiB in the assembled suite.
# Keep a finite input bound and discard completed cases while streaming it.
MAX_REPORT_BYTES = 64 * 1024 * 1024
MAX_FAILURES = 8


def nested_failure_summary(report: Path, stdout: str, stderr: str) -> str:
    parts = ["Full validation failed against the disposable PostgreSQL database."]
    try:
        if report.stat().st_size > MAX_REPORT_BYTES:
            raise ValueError("report exceeds bound")
        failures: list[str] = []
        count = 0
        for _, case in ElementTree.iterparse(report, events=("end",)):
            if case.tag != "testcase":
                continue
            for tag in ("failure", "error"):
                entry = case.find(tag)
                if entry is not None:
                    count += 1
                    if len(failures) < MAX_FAILURES:
                        node = f"{case.get('classname', '')}::{case.get('name', '')}"[:300]
                        failures.append(
                            f"\n{node}\n{entry.get('message', '')[:400]}\n"
                            f"{(entry.text or '')[-2000:]}"
                        )
            case.clear()
        parts.append(f"Nested test failures/errors: {count}")
        parts.extend(failures)
        if count > MAX_FAILURES:
            parts.append(f"Additional failures omitted: {count - MAX_FAILURES}")
    except (OSError, ValueError, ElementTree.ParseError):
        parts.append("Nested JUnit evidence unavailable or exceeds bound.")
    # Retain non-pytest failures (migration/static tools) without swallowing test evidence.
    parts.append(f"stdout tail:\n{stdout[-2000:]}\nstderr tail:\n{stderr[-2000:]}")
    return "\n".join(parts)
