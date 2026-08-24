#!/usr/bin/env python3
"""Compatibility entrypoint for the production operations audit."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Any

import production_ops_audit as audit

_ORIGINAL_CLOUD_RUN_AUDIT = audit.audit_cloud_run
_ORIGINAL_CLOUD_SQL_AUDIT = audit.audit_cloud_sql


def replace_result(name: str, passed: bool, detail: object) -> None:
    """Replace one previously recorded audit result by name."""
    status = "PASS" if passed else "FAIL"
    replacement = audit.AuditResult(name, status, audit.safe_text(detail))
    for index, result in enumerate(audit.RESULTS):
        if result.name == name:
            audit.RESULTS[index] = replacement
            return
    audit.RESULTS.append(replacement)


def audit_cloud_run(access_token: str) -> None:
    """Treat an omitted Cloud Run reconciling field as false."""
    prefix = f"projects/{audit.PROJECT_ID}/locations/{audit.REGION}"
    service = audit.cloud_run_get(
        f"{prefix}/services/{audit.WEB_SERVICE}", access_token
    )
    _ORIGINAL_CLOUD_RUN_AUDIT(access_token)
    reconciling = bool(service.get("reconciling", False))
    replace_result(
        "Cloud Run reconciliation complete",
        not reconciling,
        f"reconciling={reconciling}",
    )


def execution_status(
    execution: dict[str, Any],
) -> tuple[bool, str, datetime | None]:
    """Read execution status from the Cloud Run v2 representation."""
    condition = execution.get("terminalCondition")
    if not isinstance(condition, dict):
        condition = None
        for candidate in execution.get("conditions", []) or []:
            if candidate.get("type") in {"Completed", "Ready"}:
                condition = candidate
                break

    state = ""
    message = "no terminal condition"
    if isinstance(condition, dict):
        state = str(condition.get("state") or condition.get("status") or "")
        message = str(condition.get("message") or "completed successfully")

    success = state.casefold() in {"condition_succeeded", "true"}
    completion_time = audit.parse_time(execution.get("completionTime"))
    return success, audit.safe_text(message), completion_time


def latest_execution(job_name: str, access_token: str) -> dict[str, Any]:
    """Return the newest execution using the stable Cloud Run v2 API."""
    parent = (
        f"projects/{audit.PROJECT_ID}/locations/{audit.REGION}/jobs/{job_name}"
    )
    response = audit.cloud_run_get(
        f"{parent}/executions?pageSize=1", access_token
    )
    executions = response.get("executions", [])
    if not isinstance(executions, list) or not executions:
        raise RuntimeError(f"No executions found for Cloud Run job {job_name}")
    execution = executions[0]
    if not isinstance(execution, dict):
        raise RuntimeError(f"Unexpected execution response for {job_name}")
    return execution


def audit_scheduler() -> None:
    """Audit Scheduler and executions without preview-only gcloud commands."""
    scheduler = audit.run_json(
        [
            "gcloud",
            "scheduler",
            "jobs",
            "describe",
            audit.SCHEDULER_JOB,
            f"--project={audit.PROJECT_ID}",
            f"--location={audit.REGION}",
        ]
    )
    target = scheduler.get("httpTarget", {})
    oauth = target.get("oauthToken", {})
    expected_uri = (
        f"https://run.googleapis.com/v2/projects/{audit.PROJECT_ID}"
        f"/locations/{audit.REGION}/jobs/{audit.SYNC_JOB}:run"
    )
    audit.record(
        "Sync scheduler enabled",
        scheduler.get("state") == "ENABLED",
        scheduler.get("state"),
    )
    audit.record(
        "Sync scheduler hourly",
        scheduler.get("schedule") == "0 * * * *",
        scheduler.get("schedule"),
    )
    audit.record(
        "Sync scheduler timezone",
        scheduler.get("timeZone") == "America/Los_Angeles",
        scheduler.get("timeZone"),
    )
    audit.record(
        "Sync scheduler target exact",
        target.get("uri") == expected_uri,
        target.get("uri"),
    )
    audit.record(
        "Sync scheduler method POST",
        target.get("httpMethod") == "POST",
        target.get("httpMethod"),
    )
    scheduler_email = (
        f"ad-analyzer-scheduler@{audit.PROJECT_ID}.iam.gserviceaccount.com"
    )
    audit.record(
        "Sync scheduler uses OAuth service account",
        oauth.get("serviceAccountEmail") == scheduler_email
        and not target.get("oidcToken"),
        oauth.get("serviceAccountEmail"),
    )

    access_token = audit.run_text(["gcloud", "auth", "print-access-token"])
    sync_execution = latest_execution(audit.SYNC_JOB, access_token)
    sync_success, sync_message, sync_completed = execution_status(sync_execution)
    audit.record("Latest sync execution succeeded", sync_success, sync_message)
    if sync_completed is None:
        audit.record(
            "Latest sync execution is recent",
            False,
            "completion time unavailable",
        )
    else:
        age = datetime.now(UTC) - sync_completed
        audit.record(
            "Latest sync execution is recent",
            age <= audit.MAX_SYNC_AGE,
            f"age_minutes={age.total_seconds() / 60:.1f}",
        )

    migration_execution = latest_execution(audit.MIGRATION_JOB, access_token)
    migration_success, migration_message, _ = execution_status(
        migration_execution
    )
    audit.record(
        "Latest migration execution succeeded",
        migration_success,
        migration_message,
    )


def audit_cloud_sql() -> None:
    """Read deletion protection from the Cloud SQL Settings object."""
    _ORIGINAL_CLOUD_SQL_AUDIT()
    instance = audit.run_json(
        [
            "gcloud",
            "sql",
            "instances",
            "describe",
            audit.SQL_INSTANCE,
            f"--project={audit.PROJECT_ID}",
        ]
    )
    enabled = instance.get("settings", {}).get("deletionProtectionEnabled")
    replace_result(
        "Cloud SQL deletion protection enabled",
        enabled is True,
        enabled,
    )


def main() -> int:
    audit.audit_cloud_run = audit_cloud_run
    audit.audit_scheduler = audit_scheduler
    audit.audit_cloud_sql = audit_cloud_sql
    return audit.main()


if __name__ == "__main__":
    sys.exit(main())
