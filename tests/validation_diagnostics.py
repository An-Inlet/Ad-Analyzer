"""Bounded per-test evidence for nested validation failures, not only a stdout tail."""

from pathlib import Path
from xml.etree import ElementTree

MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_FAILURES = 8


def nested_failure_summary(report: Path, stdout: str, stderr: str) -> str:
    parts = ["Full validation failed against the disposable PostgreSQL database."]
    try:
        if report.stat().st_size > MAX_REPORT_BYTES:
            raise ValueError("report exceeds bound")
        root = ElementTree.parse(report).getroot()
        failures = []
        for case in root.iter("testcase"):
            for tag in ("failure", "error"):
                entry = case.find(tag)
                if entry is not None:
                    failures.append((case, entry))
        parts.append(f"Nested test failures/errors: {len(failures)}")
        for case, failure in failures[:MAX_FAILURES]:
            node = f"{case.get('classname', '')}::{case.get('name', '')}"[:300]
            parts.append(
                f"\n{node}\n{failure.get('message', '')[:400]}\n{(failure.text or '')[-2000:]}"
            )
        if len(failures) > MAX_FAILURES:
            parts.append(f"Additional failures omitted: {len(failures) - MAX_FAILURES}")
    except (OSError, ValueError, ElementTree.ParseError):
        parts.append("Nested JUnit evidence unavailable or exceeds bound.")
    # Retain non-pytest failures (migration/static tools) without swallowing test evidence.
    parts.append(f"stdout tail:\n{stdout[-2000:]}\nstderr tail:\n{stderr[-2000:]}")
    return "\n".join(parts)
