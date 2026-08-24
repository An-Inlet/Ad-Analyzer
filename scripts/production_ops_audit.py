#!/usr/bin/env python3
"""Run a read-only audit of the Ad Analyzer Google Cloud deployment."""

from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "totemic-alchemy-502420-p4")
PROJECT_NUMBER = os.getenv("GCP_PROJECT_NUMBER", "89443799388")
REGION = os.getenv("GCP_REGION", "us-west1")
WEB_SERVICE = os.getenv("GCP_WEB_SERVICE", "ad-analyzer-web")
SYNC_JOB = os.getenv("GCP_SYNC_JOB", "ad-analyzer-sync")
MIGRATION_JOB = os.getenv("GCP_MIGRATION_JOB", "ad-analyzer-migration")
SQL_INSTANCE = os.getenv("GCP_SQL_INSTANCE", "ad-analyzer-postgres")
SCHEDULER_JOB = os.getenv("GCP_SCHEDULER_JOB", "ad-analyzer-sync-hourly")
DASHBOARD_EMAIL = os.getenv(
    "AD_ANALYZER_EXPECTED_DASHBOARD_EMAIL", "konner@aninlet.com"
)
REPORT_PATH = Path(os.getenv("AD_ANALYZER_AUDIT_REPORT", "production-audit.json"))
MAX_SYNC_AGE = timedelta(
    minutes=int(os.getenv("AD_ANALYZER_MAX_SYNC_AGE_MINUTES", "150"))
)

WEB_ACCOUNT = f"serviceAccount:ad-analyzer-web@{PROJECT_ID}.iam.gserviceaccount.com"
SYNC_ACCOUNT = f"serviceAccount:ad-analyzer-sync@{PROJECT_ID}.iam.gserviceaccount.com"
MIGRATION_ACCOUNT = (
    f"serviceAccount:ad-analyzer-migration@{PROJECT_ID}.iam.gserviceaccount.com"
)
SCHEDULER_ACCOUNT = (
    f"serviceAccount:ad-analyzer-scheduler@{PROJECT_ID}.iam.gserviceaccount.com"
)
DEPLOYER_ACCOUNT = (
    f"serviceAccount:ad-analyzer-deployer@{PROJECT_ID}.iam.gserviceaccount.com"
)
IAP_AGENT = (
    f"serviceAccount:service-{PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"
)

EXPECTED_SECRET_ACCESS: dict[str, set[str]] = {
    "DATABASE_PASSWORD": {WEB_ACCOUNT, SYNC_ACCOUNT, MIGRATION_ACCOUNT},
    "AD_ANALYZER_API_TOKEN": {WEB_ACCOUNT},
    "GOOGLE_ADS_CLIENT_ID": {SYNC_ACCOUNT},
    "GOOGLE_ADS_CLIENT_SECRET": {SYNC_ACCOUNT},
    "GOOGLE_ADS_REFRESH_TOKEN": {SYNC_ACCOUNT},
    "GOOGLE_ADS_DEVELOPER_TOKEN": {SYNC_ACCOUNT},
}
EXPECTED_SECRET_REFERENCES: dict[str, set[str]] = {
    WEB_SERVICE: {"DATABASE_PASSWORD", "AD_ANALYZER_API_TOKEN"},
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
    f"ad-analyzer-web@{PROJECT_ID}.iam.gserviceaccount.com",
    f"ad-analyzer-sync@{PROJECT_ID}.iam.gserviceaccount.com",
    f"ad-analyzer-migration@{PROJECT_ID}.iam.gserviceaccount.com",
    f"ad-analyzer-scheduler@{PROJECT_ID}.iam.gserviceaccount.com",
}


@dataclass(frozen=True)
class AuditResult:
    name: str
    status: str
    detail: str


RESULTS: list[AuditResult] = []


def safe_text(value: object, limit: int = 500) -> str:
    return " ".join(str(value).split())[:limit]


def record(name: str, passed: bool, detail: object) -> None:
    status = "PASS" if passed else "FAIL"
    RESULTS.append(AuditResult(name, status, safe_text(detail)))


def warn(name: str, detail: object) -> None:
    RESULTS.append(AuditResult(name, "WARN", safe_text(detail)))


def run_text(args: list[str]) -> str:
    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "command failed"
        raise RuntimeError(f"{args[0]} command failed: {safe_text(detail)}")
    return completed.stdout.strip()


def run_json(args: list[str]) -> Any:
    output = run_text([*args, "--format=json"])
    return json.loads(output or "{}")


def cloud_run_get(path: str, access_token: str) -> dict[str, Any]:
    connection = http.client.HTTPSConnection("run.googleapis.com", timeout=30)
    try:
        connection.request(
            "GET",
            f"/v2/{path}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response = connection.getresponse()
        payload = response.read().decode("utf-8")
    finally:
        connection.close()
    if response.status != 200:
        raise RuntimeError(f"Cloud Run API returned HTTP {response.status}")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise RuntimeError("Cloud Run API returned an unexpected response")
    return parsed


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


def environment(
    container: dict[str, Any],
) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
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
    completed = None
    for condition in conditions or []:
        if condition.get("type") in {"Completed", "Ready"}:
            completed = condition
            break
    success = bool(
        completed and str(completed.get("status", "")).casefold() == "true"
    )
    if isinstance(completed, dict):
        message = completed.get("message") or "completed successfully"
    else:
        message = "no terminal condition"
    completion_time = parse_time(
        execution.get("completionTime")
        or nested(execution, "status", "completionTime")
    )
    return success, safe_text(message), completion_time


def audit_cloud_run(access_token: str) -> None:
    prefix = f"projects/{PROJECT_ID}/locations/{REGION}"
    service = cloud_run_get(f"{prefix}/services/{WEB_SERVICE}", access_token)
    sync = cloud_run_get(f"{prefix}/jobs/{SYNC_JOB}", access_token)
    migration = cloud_run_get(f"{prefix}/jobs/{MIGRATION_JOB}", access_token)

    record("Cloud Run IAP enabled", service.get("iapEnabled") is True, service.get("iapEnabled"))
    record(
        "Cloud Run reconciliation complete",
        service.get("reconciling") is False,
        f"reconciling={service.get('reconciling')}",
    )
    record(
        "Latest web revision ready",
        service.get("latestCreatedRevision") == service.get("latestReadyRevision"),
        (
            f"created={service.get('latestCreatedRevision')} "
            f"ready={service.get('latestReadyRevision')}"
        ),
    )

    active_traffic = [
        entry
        for entry in service.get("trafficStatuses", [])
        if int(entry.get("percent", 0)) > 0
    ]
    record(
        "Web traffic pinned to one revision",
        len(active_traffic) == 1 and int(active_traffic[0].get("percent", 0)) == 100,
        json.dumps(active_traffic, sort_keys=True),
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
    images = {
        name: str(container.get("image", ""))
        for name, container in containers.items()
    }
    record(
        "Runtime image parity",
        len(set(images.values())) == 1 and all(images.values()),
        "; ".join(f"{name}={image}" for name, image in images.items()),
    )

    plain_by_resource: dict[str, dict[str, str]] = {}
    refs_by_resource: dict[str, dict[str, tuple[str, str]]] = {}
    for resource_name, container in containers.items():
        plain, references = environment(container)
        plain_by_resource[resource_name] = plain
        refs_by_resource[resource_name] = references

    web_plain = plain_by_resource[WEB_SERVICE]
    sync_plain = plain_by_resource[SYNC_JOB]
    record(
        "Production application environment",
        web_plain.get("APP_ENV") == "production",
        web_plain.get("APP_ENV"),
    )
    record(
        "Google Ads writes disabled",
        sync_plain.get("AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED", "").casefold()
        == "false",
        sync_plain.get("AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED"),
    )
    record(
        "Google Ads execution kill switch enabled",
        sync_plain.get("AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH", "").casefold()
        == "true",
        sync_plain.get("AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH"),
    )
    record(
        "Google Ads account allowlist empty",
        not sync_plain.get("AD_ANALYZER_ALLOWED_EXECUTION_ACCOUNT_IDS", "").strip(),
        "empty or absent",
    )
    record(
        "Google Ads mutation allowlist empty",
        not sync_plain.get("AD_ANALYZER_ALLOWED_GOOGLE_ADS_MUTATIONS", "").strip(),
        "empty or absent",
    )

    expected_audience = (
        f"/projects/{PROJECT_NUMBER}/locations/{REGION}/services/{WEB_SERVICE}"
    )
    record(
        "Dashboard IAP audience exact",
        web_plain.get("AD_ANALYZER_IAP_AUDIENCE") == expected_audience,
        web_plain.get("AD_ANALYZER_IAP_AUDIENCE"),
    )
    allowed_emails = {
        item.strip().casefold()
        for item in web_plain.get("AD_ANALYZER_PLATFORM_ADMIN_EMAILS", "").split(",")
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
            valid_start = variable_name[:1].isalpha() or variable_name.startswith("_")
            valid_body = all(char.isalnum() or char == "_" for char in variable_name)
            if not variable_name or not valid_start or not valid_body:
                malformed.append(f"{resource_name}:{variable_name!r}")
    record(
        "Runtime environment variable names valid",
        not malformed,
        "none" if not malformed else "; ".join(malformed),
    )

    for resource_name, expected_names in EXPECTED_SECRET_REFERENCES.items():
        references = refs_by_resource[resource_name]
        matching_names = set(references) == expected_names
        matching_targets = all(
            name == secret for name, (secret, _) in references.items()
        )
        numeric_versions = all(
            version.isdigit() for _, version in references.values()
        )
        detail = "; ".join(
            f"{name}->{secret}:{version}"
            for name, (secret, version) in sorted(references.items())
        )
        record(
            f"{resource_name} secret references pinned",
            matching_names and matching_targets and numeric_versions,
            detail,
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
        ",".join(sorted(public_members)) or "none",
    )
    invokers = role_members(service_policy, "roles/run.invoker")
    record(
        "IAP service agent can invoke web",
        IAP_AGENT in invokers,
        ",".join(sorted(invokers)),
    )

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
    expected = {f"user:{DASHBOARD_EMAIL}"}
    record(
        "IAP dashboard accessors exact",
        accessors == expected,
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
        f"https://run.googleapis.com/v2/projects/{PROJECT_ID}/locations/{REGION}"
        f"/jobs/{SYNC_JOB}:run"
    )
    record("Sync scheduler enabled", scheduler.get("state") == "ENABLED", scheduler.get("state"))
    record("Sync scheduler hourly", scheduler.get("schedule") == "0 * * * *", scheduler.get("schedule"))
    record(
        "Sync scheduler timezone",
        scheduler.get("timeZone") == "America/Los_Angeles",
        scheduler.get("timeZone"),
    )
    record(
        "Sync scheduler target exact",
        target.get("uri") == expected_uri,
        target.get("uri"),
    )
    record(
        "Sync scheduler method POST",
        target.get("httpMethod") == "POST",
        target.get("httpMethod"),
    )
    scheduler_email = f"ad-analyzer-scheduler@{PROJECT_ID}.iam.gserviceaccount.com"
    record(
        "Sync scheduler uses OAuth service account",
        oauth.get("serviceAccountEmail") == scheduler_email
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
    success, message, _ = execution_status(migration_execution)
    record("Latest migration execution succeeded", success, message)


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
    ip_config = settings.get("ipConfiguration", {})
    backup = settings.get("backupConfiguration", {})
    networks = [item for item in ip_config.get("authorizedNetworks", []) or [] if item]

    record("Cloud SQL state runnable", instance.get("state") == "RUNNABLE", instance.get("state"))
    record(
        "Cloud SQL connector enforcement required",
        settings.get("connectorEnforcement") == "REQUIRED",
        settings.get("connectorEnforcement"),
    )
    record(
        "Cloud SQL authorized networks empty",
        not networks,
        json.dumps(networks, sort_keys=True) if networks else "none",
    )
    record(
        "Cloud SQL encrypted connections required",
        ip_config.get("sslMode") == "ENCRYPTED_ONLY",
        ip_config.get("sslMode"),
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
        ",".join(sorted(accounts_with_keys)) or "none",
    )

    project_policy = run_json(
        ["gcloud", "projects", "get-iam-policy", PROJECT_ID]
    )
    secret_accessors = role_members(
        project_policy, "roles/secretmanager.secretAccessor"
    )
    record(
        "No project-wide Secret Manager accessors",
        not secret_accessors,
        ",".join(sorted(secret_accessors)) or "none",
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
        "Scheduler can invoke sync job",
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
                age_days = (datetime.now(UTC) - created).days
                warn(f"{secret_name} rotation review", f"age_days={age_days}")

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
        short_name = runtime_account.split("@", 1)[0]
        record(
            f"Deployer actAs scoped to {short_name}",
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
    REPORT_PATH.write_text(
        json.dumps(report, indent=2) + chr(10), encoding="utf-8"
    )

    lines = [
        "# Ad Analyzer production operations audit",
        "",
        f"Generated: `{generated_at}`",
        "",
        (
            f"**{len(failures)} failure(s), {len(warnings)} warning(s), "
            f"{len(RESULTS)} total checks.**"
        ),
        "",
        "| Status | Check | Detail |",
        "|---|---|---|",
    ]
    for result in RESULTS:
        detail = result.detail.replace("|", "\\|")
        lines.append(f"| {result.status} | {result.name} | `{detail}` |")
    summary = chr(10).join(lines) + chr(10)
    print(summary)

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(summary)


def main() -> int:
    try:
        access_token = run_text(["gcloud", "auth", "print-access-token"])
        audit_cloud_run(access_token)
    except Exception as exc:  # noqa: BLE001
        record("Cloud Run configuration audit", False, exc)

    audits = (
        ("Cloud Run IAM audit", audit_cloud_run_iam),
        ("Scheduler and execution audit", audit_scheduler),
        ("Cloud SQL audit", audit_cloud_sql),
        ("IAM and Secret Manager audit", audit_iam_and_secrets),
    )
    for name, audit in audits:
        try:
            audit()
        except Exception as exc:  # noqa: BLE001
            record(name, False, exc)

    write_report()
    has_failures = any(result.status == "FAIL" for result in RESULTS)
    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
