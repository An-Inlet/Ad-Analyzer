"""Bounded per-test evidence for nested validation failures, not only a stdout tail."""

from pathlib import Path
from xml.etree import ElementTree

# Parameterized boundary-test IDs alone exceed 16 MiB in the assembled suite.
# Keep a finite input bound and discard completed cases while streaming it.
MAX_REPORT_BYTES = 64 * 1024 * 1024
MAX_FAILURES = 8
MAX_ARTIFACT_BYTES = 256 * 1024


def nested_failure_summary(report: Path, stdout: str, stderr: str) -> str:
    parts = ["Full validation failed against the disposable PostgreSQL database."]
    try:
        if report.stat().st_size > MAX_REPORT_BYTES:
            raise ValueError("report exceeds bound")
        failures: list[str] = []
        count = 0
        skips: dict[str, int] = {}
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
            skipped = case.find("skipped")
            if skipped is not None:
                reason = skipped.get("message", "unspecified skip")[:300]
                if reason not in skips and len(skips) >= 32:
                    reason = "Additional skip reasons omitted"
                skips[reason] = skips.get(reason, 0) + 1
            case.clear()
        parts.append(f"Nested test failures/errors: {count}")
        parts.extend(failures)
        if count > MAX_FAILURES:
            parts.append(f"Additional failures omitted: {count - MAX_FAILURES}")
        parts.append(f"Nested skipped tests: {sum(skips.values())}")
        parts.extend(f"Skipped {number}: {reason}" for reason, number in sorted(skips.items()))
    except (OSError, ValueError, ElementTree.ParseError):
        parts.append("Nested JUnit evidence unavailable or exceeds bound.")
    # Retain non-pytest failures (migration/static tools) without swallowing test evidence.
    parts.append(f"stdout tail:\n{stdout[-2000:]}\nstderr tail:\n{stderr[-2000:]}")
    return "\n".join(parts)


def collect_nested_diagnostics(root: Path, output: Path) -> None:
    """Persist only bounded summaries, never the full parameterized XML or logs."""
    base = root.resolve()
    reports: set[Path] = set()
    summaries = []
    candidates = [
        root / "aggregate.xml",
        *sorted(root.glob("test_full_validation_can_run_t*/nested-full-*.xml")),
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        report = candidate.resolve()
        if not report.is_relative_to(base) or report in reports:
            continue
        reports.add(report)
        summaries.append(f"Report: {report.name}\n{nested_failure_summary(report, '', '')}")
        if len(reports) == 2:
            break
    text = "\n\n".join(summaries) if summaries else "No nested JUnit report was produced."
    bounded = text.encode("utf-8")[:MAX_ARTIFACT_BYTES].decode("utf-8", errors="ignore")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(bounded, encoding="utf-8")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Collect bounded nested validation evidence")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    collect_nested_diagnostics(arguments.root, arguments.output)
