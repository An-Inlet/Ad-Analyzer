#!/usr/bin/env python3
"""Read-only production audit for the Denticode Google Cloud deployment.

The script intentionally retrieves configuration and IAM metadata only. It never reads
Secret Manager payloads, never mutates Google Ads, and never changes Google Cloud state.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "totemic-alchemy-502420-p4")
PROJECT_NUMBER = os.getenv("GCP_PROJECT_NUMBER", "89443799388")
REGION = os.getenv("GCP_REGION", "us-west1")
WEB_SERVICE = os.getenv("GCP_WEB_SERVICE", "denticode-web")
SYNC_JOB = os.getenv("GCP_SYNC_JOB", "denticode-sync")
MIGRATION_JOB = os.getenv("GCP_MIGRATION_JOB", "denticode-migration")
SQL_INSTANCE = os.getenv("GCP_SQL_INSTANCE", "denticode-analyzer-postgres")
SCHEDULER_JOB = os.getenv("GCP_SCHEDULER_JOB", "denticode-sync-hourly")
DASHBOARD_EMAIL = os.getenv("DENTICODE_EXPECTED_DASHBOARD_EMAIL", "konner@aninlet.com")
REPORT_PATH = Path(os.getenv("DENTICODE_AUDIT_REPORT", "production-audit.json"))
MAX_SYNC_AGE = timedelta(minutes=int(os.getenv("DENTICODE_MAX_SYNC_AGE_MINUTES", "150")))

WEB_ACCOUNT = f"serviceAccount:denticode-web@{PROJECT_ID}.iam.gserviceaccount.com"
SYNC_ACCOUNT = f"serviceAccount:denticode-sync@{PROJECT_ID}.iam.gserviceaccount.com"
MIGRATION_ACCOUNT = (
    f"serviceAccount:denticode-migration@{PROJECT_ID}.iam.gserviceaccount.com"
)
SCHEDULER_ACCOUNT = (
    f"serviceAccount:denticode-scheduler@{PROJECT_ID}.iam.gserviceaccount.com"
)
DEPLOYER_ACCOUNT = (
    f"serviceAccount:denticode-deployer@{PROJECT_ID}.iam.gserviceaccount.com"
)
IAP_AGENT = f"serviceAccount:service-{PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"

EXPECTED_SECRET_ACCESS: dict[str, set[str]] = {
    "DATABASE_PASSWORD": {WEB_ACCOUNT, SYNC_ACCOUNT, MIGRATION_ACCOUNT},
    "DENTICODE_API_TOKEN": {WEB_ACCOUNT},
    "GOOGLE_ADS_CLIENT_ID": {SYNC_ACCOUNT},
    "GOOGLE_ADS_CLIENT_SECRET": {SYNC_ACCOUNT},
    "GOOGLE_ADS_REFRESH_TOKEN": {SYNC_ACCOUNT},
    "GOOGLE_ADS_DEVELOPER_TOKEN": {SYNC_ACCOUNT},
}
EXPECTED_SECRET_REFERENCES: dict[str, set[str]] = {
    WEB_SERVICE: {"DATABASE_PASSWORD", "DENTICODE_API_TOKEN"},
    SYNC_JOB: {
        "DATABASE_PASSWORD",
        "GOOGLE_ADS_CLIENT_ID",
        "GOOGLE_ADS_CLIENT_SECRET",
        "GOOGLE_ADS_REFRESH_TOKEN",
        "GOOGLE_ADS_DEVELOPER_TOKEN",
    },
    MIGRATION_JOB: {"DATABASE_PASSWORD"},
}
RUNTIME_ACCOUNTS = {
    f"denticode-web@{PROJECT_ID}.iam.gserviceaccount.com",
    f"denticode-sync@{PROJECT_ID}.iam.gserviceaccount.com",
    f"denticode-migration@{PROJECT_ID}.iam.gserviceaccount.com",
    f"denticode-scheduler@{PROJECT_ID}.iam.gserviceaccount.com",
}


@dataclass(frozen=True)
class AuditResult:
    name: str
    status: str
    detail: str


RESULTS: list[AuditResult] = []


def _safe_text(value: object, limit: int = 500) -> str:
    text = " ".join(str(value).split())
    return text[:limit]


def record(name: str, passed: bool, detail: object) -> None:
    RESULTS.append(
        AuditResult(name=name, status="PASS" if passed else "FAIL", detail=_safe_text(detail))
    )


def warn(name: str, detail: object) -> None:
    RESULTS.append(AuditResult(name=name, status="WARN", detail=_safe_text(detail)))


def run_text(args: list[str]) -> str:
    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip() or "command failed"
        raise RuntimeError(f"{args[0]} command failed: {_safe_text(error)}")
    return completed.stdout.strip()


def run_json(args: list[str]) -> Any:
    output = run_text([*args, "--format=json"])
    return json.loads(output or "{}")


def api_get(path: str, access_token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://run.googleapis.com/v2/{path}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cloud Run API request failed: {_safe_text(exc)}") from exc


def nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def role_members(policy: dict[str, Any], role: str) -> set[str]:
    members: set[str] = set()
    for binding in policy.get("bindings", []):
        if binding.get("role") == role:
            members.update(binding.get("members", []))
    return members


def environment(container: dict[str, Any]) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    plain: dict[str, str] = {}
    secret_refs: dict[str, tuple[str, str]] = {}
    for item in container.get("env", []):
        name = str(item.get("name", ""))
        if "value" in item:
            plain[name] = str(item.get("value", ""))
        reference = nested(item, "valueSource", "secretKeyRef", default={})
        if isinstance(reference, dict) and reference:
            secret_refs[name] = (
                str(reference.get("secret", "")),
                str(reference.get("version", "")),
            )
    return plain, secret_refs


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def execution_status(execution: dict[str, Any]) -> tuple[bool, str, datetime | None]:
    conditions = execution.get("conditions") or nested(
        execution, "status", "conditions", default=[]
    )
    completed_condition = None
    for condition in conditions or []:
        if condition.get("type") in {"Completed", "Ready"}:
            completed_condition = condition
            break
    success = bool(
        completed_condition
        and str(completed_condition.get("status", "")).casefold() == "true"
    )
    message = (
        completed_condition.get("message")
        if isinstance(completed_condition, dict)
        else "no terminal condition"
    )
    completion_time = parse_time(
        execution.get("completionTime")
        or nested(execution, "status", "completionTime")
    )
    return success, _safe_text(message or "completed successfully"), completion_time


def audit_cloud_run(access_token: str) -> None:
    service = api_get(
        f"projects/{PROJECT_ID}/locations/{REGION}/services/{WEB_SERVICE}", access_token
    )
    sync = api_get(
        f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{SYNC_JOB}", access_token
    )
    migration = api_get(
        f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{MIGRATION_JOB}", access_token
    )

    record("Cloud Run IAP enabled", service.get("iapEnabled") is True, service.get("iapEnabled"))
    record(
        "Cloud Run reconciliation complete",
        service.get("reconciling") is False,
        f"reconciling={service.get('reconciling')}",
    )
    record(
        "Latest web revision ready",
        service.get("latestCreatedRevision") == service.get("latestReadyRevision"),
        f"created={service.get('latestCreatedRevision')} ready={service.get('latestReadyRevision')}",
    )

    traffic = service.get("trafficStatuses", [])
    traffic_100 = [entry for entry in traffic if int(entry.get("percent", 0)) == 100]
    old_traffic = [entry for entry in traffic if int(entry.get("percent", 0)) > 0]
    record(
        "Web traffic pinned to one revision",
        len(traffic_100) == 1 and len(old_traffic) == 1,
        json.dumps(old_traffic, sort_keys=True),
    )

    web_container = nested(service, "template", "containers", default=[{}])[0]
    sync_container = nested(sync, "template", "template", "containers", default=[{}])[0]
    migration_container = nested(
        migration, "template", "template", "containers", default=[{}]
    )[0]
    containers = {
        WEB_SERVICE: web_container,
        SYNC_JOB: sync_container,
        MIGRATION_JOB: migration_container,
    }
    images = {name: str(container.get("image", "")) for name, container in containers.items()}
    record(
        "Runtime image parity",
        len(set(images.values())) == 1 and all(images.values()),
        "; ".join(f"{name}={image}" for name, image in images.items()),
    )

    web_plain, web_refs = environment(web_container)
    sync_plain, sync_refs = environment(sync_container)
    migration_plain, migration_refs = environment(migration_container)
    plain_by_resource = {
        WEB_SERVICE: web_plain,
        SYNC_JOB: sync_plain,
        MIGRATION_JOB: migration_plain,
    }
    refs_by_resource = {
        WEB_SERVICE: web_refs,
        SYNC_JOB: sync_refs,
        MIGRATION_JOB: migration_refs,
    }

    record("Production application environment", web_plain.get("APP_ENV") == "production", web_plain.get("APP_ENV"))
    record(
        "Google Ads writes disabled",
        sync_plain.get("DENTICODE_GOOGLE_ADS_WRITE_ENABLED", "").casefold() == "false",
        sync_plain.get("DENTICODE_GOOGLE_ADS_WRITE_ENABLED"),
    )
    record(
        "Google Ads execution kill switch enabled",
        sync_plain.get("DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH", "").casefold()
        == "true",
        sync_plain.get("DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH"),
    )
    record(
        "Google Ads account allowlist empty",
        not sync_plain.get("DENTICODE_ALLOWED_GOOGLE_ADS_ACCOUNTS", "").strip(),
        "empty" if not sync_plain.get("DENTICODE_ALLOWED_GOOGLE_ADS_ACCOUNTS", "").strip() else "configured",
    )
    record(
        "Google Ads mutation allowlist empty",
        not sync_plain.get("DENTICODE_ALLOWED_GOOGLE_ADS_MUTATIONS", "").strip(),
        "empty" if not sync_plain.get("DENTICODE_ALLOWED_GOOGLE_ADS_MUTATIONS", "").strip() else "configured",
    )
    record(
        "Dashboard IAP audience exact",
        web_plain.get("DENTICODE_IAP_AUDIENCE")
        == f"/projects/{PROJECT_NUMBER}/locations/{REGION}/services/{WEB_SERVICE}",
        web_plain.get("DENTICODE_IAP_AUDIENCE"),
    )
    allowed_emails = {
        item.strip().casefold()
        for item in web_plain.get("DENTICODE_DASHBOARD_ALLOWED_EMAILS", "").split(",")
        if item.strip()
    }
    record(
        "Dashboard application allowlist exact",
        allowed_emails == {DASHBOARD_EMAIL.casefold()},
        ",".join(sorted(allowed_emails)),
    )
    record(
        "Web maximum instances restricted",
        nested(service, "template", "scaling", "maxInstanceCount") == 1,
        nested(service, "template", "scaling", "maxInstanceCount"),
    )

    malformed: list[str] = []
    for resource_name, values in plain_by_resource.items():
        for variable_name in values:
            if not variable_name or not (
                variable_name[0].isalpha() or variable_name[0] == "_"
            ) or not all(char.isalnum() or char == "_" for char in variable_name):
                malformed.append(f"{resource_name}:{variable_name!r}")
    record(
        "Runtime environment variable names valid",
        not malformed,
        "none" if not malformed else "; ".join(malformed),
    )

    for resource_name, expected_names in EXPECTED_SECRET_REFERENCES.items():
        actual_refs = refs_by_resource[resource_name]
        numeric_versions = all(version.isdigit() for _, version in actual_refs.values())
        matching_names = set(actual_refs) == expected_names
        matching_targets = all(name == secret for name, (secret, _) in actual_refs.items())
        record(
            f"{resource_name} secret references pinned",
            matching_names and matching_targets and numeric_versions,
            "; ".join(
                f"{name}->{secret}:{version}"
                for name, (secret, version) in sorted(actual_refs.items())
            ),
        )


def audit_cloud_run_iam() -> None:
    service_policy = run_json(
        [
            "gcloud",
            "run",
            "services",
            "get-iam-policy",
            WEB_SERVICE,
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
        ]
    )
    public_members = {
        member
        for binding in service_policy.get("bindings", [])
        for member in binding.get("members", [])
        if member in {"allUsers", "allAuthenticatedUsers"}
    }
    record(
        "Cloud Run service has no public principal",
        not public_members,
        "none" if not public_members else ",".join(sorted(public_members)),
    )
    invokers = role_members(service_policy, "roles/run.invoker")
    record("IAP service agent can invoke web", IAP_AGENT in invokers, ",".join(sorted(invokers)))

    iap_policy = run_json(
        [
            "gcloud",
            "iap",
            "web",
            "get-iam-policy",
            f"--project={PROJECT_ID}",
            "--resource-type=cloud-run",
            f"--service={WEB_SERVICE}",
            f"--region={REGION}",
        ]
    )
    accessors = role_members(iap_policy, "roles/iap.httpsResourceAccessor")
    expected_accessor = {f"user:{DASHBOARD_EMAIL}"}
    record(
        "IAP dashboard accessors exact",
        accessors == expected_accessor,
        ",".join(sorted(accessors)),
    )


def audit_scheduler() -> None:
    scheduler = run_json(
        [
            "gcloud",
            "scheduler",
            "jobs",
            "describe",
            SCHEDULER_JOB,
            f"--project={PROJECT_ID}",
            f"--location={REGION}",
        ]
    )
    target = scheduler.get("httpTarget", {})
    oauth = target.get("oauthToken", {})
    expected_uri = (
        f"https://run.googleapis.com/v2/projects/{PROJECT_ID}/locations/{REGION}/jobs/{SYNC_JOB}:run"
    )
    record("Sync scheduler enabled", scheduler.get("state") == "ENABLED", scheduler.get("state"))
    record("Sync scheduler hourly", scheduler.get("schedule") == "0 * * * *", scheduler.get("schedule"))
    record(
        "Sync scheduler timezone",
        scheduler.get("timeZone") == "America/Los_Angeles",
        scheduler.get("timeZone"),
    )
    record("Sync scheduler target exact", target.get("uri") == expected_uri, target.get("uri"))
    record("Sync scheduler method POST", target.get("httpMethod") == "POST", target.get("httpMethod"))
    record(
        "Sync scheduler uses OAuth service account",
        oauth.get("serviceAccountEmail")
        == f"denticode-scheduler@{PROJECT_ID}.iam.gserviceaccount.com"
        and not target.get("oidcToken"),
        oauth.get("serviceAccountEmail"),
    )

    sync_execution = run_json(
        [
            "gcloud",
            "run",
            "jobs",
            "executions",
            "describe-latest",
            f"--job={SYNC_JOB}",
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
        ]
    )
    sync_success, sync_message, sync_completed = execution_status(sync_execution)
    record("Latest sync execution succeeded", sync_success, sync_message)
    if sync_completed is None:
        record("Latest sync execution is recent", False, "completion time unavailable")
    else:
        age = datetime.now(UTC) - sync_completed
        record(
            "Latest sync execution is recent",
            age <= MAX_SYNC_AGE,
            f"age_minutes={age.total_seconds() / 60:.1f}",
        )

    migration_execution = run_json(
        [
            "gcloud",
            "run",
            "jobs",
            "executions",
            "describe-latest",
            f"--job={MIGRATION_JOB}",
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
        ]
    )
    migration_success, migration_message, _ = execution_status(migration_execution)
    record("Latest migration execution succeeded", migration_success, migration_message)


def audit_cloud_sql() -> None:
    instance = run_json(
        [
            "gcloud",
            "sql",
            "instances",
            "describe",
            SQL_INSTANCE,
            f"--project={PROJECT_ID}",
        ]
    )
    settings = instance.get("settings", {})
    ip_configuration = settings.get("ipConfiguration", {})
    backup = settings.get("backupConfiguration", {})
    authorized_networks = [
        network
        for network in ip_configuration.get("authorizedNetworks", []) or []
        if network
    ]
    record("Cloud SQL state runnable", instance.get("state") == "RUNNABLE", instance.get("state"))
    record(
        "Cloud SQL connector enforcement required",
        settings.get("connectorEnforcement") == "REQUIRED",
        settings.get("connectorEnforcement"),
    )
    record(
        "Cloud SQL authorized networks empty",
        not authorized_networks,
        "none" if not authorized_networks else json.dumps(authorized_networks, sort_keys=True),
    )
    record(
        "Cloud SQL encrypted connections required",
        ip_configuration.get("sslMode") == "ENCRYPTED_ONLY",
        ip_configuration.get("sslMode"),
    )
    record("Cloud SQL backups enabled", backup.get("enabled") is True, backup.get("enabled"))
    record(
        "Cloud SQL point-in-time recovery enabled",
        backup.get("pointInTimeRecoveryEnabled") is True,
        backup.get("pointInTimeRecoveryEnabled"),
    )
    record(
        "Cloud SQL deletion protection enabled",
        instance.get("deletionProtectionEnabled") is True,
        instance.get("deletionProtectionEnabled"),
    )
    record(
        "Cloud SQL storage auto-increase enabled",
        settings.get("storageAutoResize") is True,
        settings.get("storageAutoResize"),
    )


def audit_iam_and_secrets() -> None:
    service_accounts = run_json(
        ["gcloud", "iam", "service-accounts", "list", f"--project={PROJECT_ID}"]
    )
    accounts_with_keys: list[str] = []
    for service_account in service_accounts:
        email = service_account.get("email")
        if not email:
            continue
        keys = run_json(
            [
                "gcloud",
                "iam",
                "service-accounts",
                "keys",
                "list",
                f"--iam-account={email}",
                f"--project={PROJECT_ID}",
                "--managed-by=user",
            ]
        )
        if keys:
            accounts_with_keys.append(str(email))
    record(
        "No user-managed service account keys",
        not accounts_with_keys,
        "none" if not accounts_with_keys else ",".join(sorted(accounts_with_keys)),
    )

    project_policy = run_json(
        ["gcloud", "projects", "get-iam-policy", PROJECT_ID]
    )
    project_secret_accessors = role_members(
        project_policy, "roles/secretmanager.secretAccessor"
    )
    record(
        "No project-wide Secret Manager accessors",
        not project_secret_accessors,
        "none" if not project_secret_accessors else ",".join(sorted(project_secret_accessors)),
    )
    project_invokers = role_members(project_policy, "roles/run.invoker")
    record(
        "Scheduler lacks project-wide Run Invoker",
        SCHEDULER_ACCOUNT not in project_invokers,
        ",".join(sorted(project_invokers)) or "none",
    )
    project_act_as = role_members(project_policy, "roles/iam.serviceAccountUser")
    record(
        "Deployer lacks project-wide Service Account User",
        DEPLOYER_ACCOUNT not in project_act_as,
        ",".join(sorted(project_act_as)) or "none",
    )

    sync_policy = run_json(
        [
            "gcloud",
            "run",
            "jobs",
            "get-iam-policy",
            SYNC_JOB,
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
        ]
    )
    sync_invokers = role_members(sync_policy, "roles/run.invoker")
    record(
        "Scheduler can invoke only sync job",
        SCHEDULER_ACCOUNT in sync_invokers,
        ",".join(sorted(sync_invokers)),
    )

    for secret_name, expected_members in EXPECTED_SECRET_ACCESS.items():
        policy = run_json(
            [
                "gcloud",
                "secrets",
                "get-iam-policy",
                secret_name,
                f"--project={PROJECT_ID}",
            ]
        )
        actual_members = role_members(policy, "roles/secretmanager.secretAccessor")
        record(
            f"{secret_name} access matrix exact",
            actual_members == expected_members,
            ",".join(sorted(actual_members)),
        )

        versions = run_json(
            [
                "gcloud",
                "secrets",
                "versions",
                "list",
                secret_name,
                f"--project={PROJECT_ID}",
            ]
        )
        enabled = [
            version
            for version in versions
            if str(version.get("state", "")).casefold() == "enabled"
        ]
        record(
            f"{secret_name} has one enabled version",
            len(enabled) == 1,
            f"enabled_versions={len(enabled)}",
        )
        if enabled:
            created = parse_time(enabled[0].get("createTime"))
            if created and datetime.now(UTC) - created > timedelta(days=365):
                warn(
                    f"{secret_name} rotation review",
                    f"enabled version age_days={(datetime.now(UTC) - created).days}",
                )

    for runtime_account in sorted(RUNTIME_ACCOUNTS):
        policy = run_json(
            [
                "gcloud",
                "iam",
                "service-accounts",
                "get-iam-policy",
                runtime_account,
                f"--project={PROJECT_ID}",
            ]
        )
        act_as_members = role_members(policy, "roles/iam.serviceAccountUser")
        record(
            f"Deployer actAs scoped to {runtime_account.split('@', 1)[0]}",
            DEPLOYER_ACCOUNT in act_as_members,
            ",".join(sorted(act_as_members)),
        )


def write_report() -> None:
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    failures = [result for result in RESULTS if result.status == "FAIL"]
    warnings = [result for result in RESULTS if result.status == "WARN"]
    report = {
        "generated_at": generated_at,
        "project_id": PROJECT_ID,
        "region": REGION,
        "summary": {
            "checks": len(RESULTS),
            "failures": len(failures),
            "warnings": len(warnings),
        },
        "results": [asdict(result) for result in RESULTS],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Denticode production operations audit",
        "",
        f"Generated: `{generated_at}`",
        "",
        f"**{len(failures)} failure(s), {len(warnings)} warning(s), {len(RESULTS)} total checks.**",
        "",
        "| Status | Check | Detail |",
        "|---|---|---|",
    ]
    for result in RESULTS:
        detail = result.detail.replace("|", "\\|")
        lines.append(f"| {result.status} | {result.name} | `{detail}` |")
    summary = "\n".join(lines) + "\n"
    print(summary)

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(summary)


def main() -> int:
    try:
        access_token = run_text(["gcloud", "auth", "print-access-token"])
        audit_cloud_run(access_token)
    except Exception as exc:  # noqa: BLE001 - audit must record infrastructure failures
        record("Cloud Run configuration audit", False, exc)

    for name, audit in (
        ("Cloud Run IAM audit", audit_cloud_run_iam),
        ("Scheduler and execution audit", audit_scheduler),
        ("Cloud SQL audit", audit_cloud_sql),
        ("IAM and Secret Manager audit", audit_iam_and_secrets),
    ):
        try:
            audit()
        except Exception as exc:  # noqa: BLE001 - audit must report, not hide, failures
            record(name, False, exc)

    write_report()
    return 1 if any(result.status == "FAIL" for result in RESULTS) else 0


if __name__ == "__main__":
    sys.exit(main())
