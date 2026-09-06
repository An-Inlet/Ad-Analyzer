"""Prepare a neutral, cost-capped Cloud Run service from an existing service export."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

PLATFORM_SUFFIXES = {
    "WORKSPACE_ID",
    "API_TOKEN",
    "CRM_WEBHOOK_SECRET",
    "CRM_PUBSUB_PROJECT_ID",
    "CRM_PUBSUB_TOPIC_ID",
    "CRM_PUBSUB_SUBSCRIPTION_ID",
    "DASHBOARD_ALLOW_INSECURE_LOCAL_HTTP",
    "IAP_AUDIENCE",
    "PLATFORM_ADMIN_EMAILS",
    "GITHUB_CONTROL_TOKEN",
    "GITHUB_CONTROL_REPOSITORY",
    "SYNC_INTERVAL_MINUTES",
    "SYNC_RUN_IMMEDIATELY",
    "SYNC_MAX_ATTEMPTS",
    "SYNC_RETRY_BASE_SECONDS",
    "SYNC_RETRY_MAX_SECONDS",
    "SYNC_STALE_AFTER_MINUTES",
    "SYNC_ADVISORY_LOCK_KEY",
    "SYNC_LOCK_KEY",
    "GOOGLE_ADS_WRITE_ENABLED",
    "GOOGLE_ADS_EXECUTION_KILL_SWITCH",
    "ALLOWED_EXECUTION_ACCOUNT_IDS",
    "ALLOWED_GOOGLE_ADS_MUTATIONS",
    "REQUIRED_SECRET_NAMES",
    "SECRET_REFERENCE_PREFIX",
    "WEB_CONCURRENCY",
    "WORKER_CONCURRENCY",
    "SCHEDULER_CONCURRENCY",
    "WEB_TIMEOUT_SECONDS",
    "WORKER_TIMEOUT_SECONDS",
    "SCHEDULER_TIMEOUT_SECONDS",
    "MIGRATION_TIMEOUT_SECONDS",
    "GRACEFUL_SHUTDOWN_SECONDS",
}
SENSITIVE_ENV_MARKERS = ("TOKEN", "PASSWORD", "SECRET")
SENSITIVE_EXCEPTIONS = {
    "AD_ANALYZER_REQUIRED_SECRET_NAMES",
    "AD_ANALYZER_SECRET_REFERENCE_PREFIX",
}
SERVER_METADATA_KEYS = {
    "creationTimestamp",
    "deletionGracePeriodSeconds",
    "deletionTimestamp",
    "generation",
    "managedFields",
    "resourceVersion",
    "selfLink",
    "uid",
}


class CutoverConfigError(ValueError):
    """Raised when an existing service cannot be cloned without weakening controls."""


def _template(service: dict[str, Any]) -> dict[str, Any]:
    try:
        return service["spec"]["template"]
    except (KeyError, TypeError) as exc:
        raise CutoverConfigError("Cloud Run service export has no template.") from exc


def _template_spec(service: dict[str, Any]) -> dict[str, Any]:
    template = _template(service)
    spec = template.get("spec", template)
    if not isinstance(spec, dict):
        raise CutoverConfigError("Cloud Run service template has no specification.")
    return spec


def _container(service: dict[str, Any]) -> dict[str, Any]:
    containers = _template_spec(service).get("containers")
    if not isinstance(containers, list) or len(containers) != 1:
        raise CutoverConfigError("Expected exactly one Cloud Run web container.")
    container = containers[0]
    if not isinstance(container, dict):
        raise CutoverConfigError("Cloud Run container configuration is invalid.")
    return container


def _env_entries(service: dict[str, Any]) -> list[dict[str, Any]]:
    env = _container(service).get("env", [])
    if not isinstance(env, list):
        raise CutoverConfigError("Cloud Run environment configuration is invalid.")
    return [entry for entry in env if isinstance(entry, dict)]


def _canonical_env_name(name: str) -> str | None:
    if name.endswith("_DASHBOARD_ALLOWED_EMAILS"):
        return "AD_ANALYZER_PLATFORM_ADMIN_EMAILS"
    if name.startswith("AD_ANALYZER_"):
        return name
    for suffix in sorted(PLATFORM_SUFFIXES, key=len, reverse=True):
        if name.endswith(f"_{suffix}"):
            return f"AD_ANALYZER_{suffix}"
    if name.endswith("_IMAGE_TAG") or name.endswith("_HTTP_BIND"):
        return None
    return name


def _uses_secret_reference(entry: dict[str, Any]) -> bool:
    value_from = entry.get("valueFrom") or entry.get("valueSource")
    return isinstance(value_from, dict) and isinstance(value_from.get("secretKeyRef"), dict)


def _rewrite_required_secrets(value: str) -> str:
    rewritten: list[str] = []
    for item in value.split(","):
        name = item.strip()
        if not name:
            continue
        canonical = _canonical_env_name(name)
        rewritten.append(canonical or name)
    return ",".join(dict.fromkeys(rewritten))


def _neutral_environment(
    service: dict[str, Any],
    *,
    target_service: str,
    project_number: str,
    region: str,
    repository: str,
) -> list[dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for source_entry in _env_entries(service):
        source_name = source_entry.get("name")
        if not isinstance(source_name, str):
            raise CutoverConfigError("Cloud Run environment entry has no name.")
        target_name = _canonical_env_name(source_name)
        if target_name is None:
            continue
        entry = copy.deepcopy(source_entry)
        entry["name"] = target_name
        if (
            target_name not in SENSITIVE_EXCEPTIONS
            and any(marker in target_name for marker in SENSITIVE_ENV_MARKERS)
            and "value" in entry
            and not _uses_secret_reference(entry)
        ):
            raise CutoverConfigError(
                f"Sensitive environment variable {target_name} is not Secret Manager-backed."
            )
        if target_name == "DATABASE_URL" and "value" in entry:
            raise CutoverConfigError("DATABASE_URL must not be copied as a plaintext value.")
        if target_name == "AD_ANALYZER_REQUIRED_SECRET_NAMES" and "value" in entry:
            entry["value"] = _rewrite_required_secrets(str(entry["value"]))
        mapped[target_name] = entry

    def plain(name: str, value: str) -> None:
        mapped[name] = {"name": name, "value": value}

    plain("APP_ENV", "production")
    plain(
        "AD_ANALYZER_IAP_AUDIENCE",
        f"/projects/{project_number}/locations/{region}/services/{target_service}",
    )
    plain("AD_ANALYZER_GITHUB_CONTROL_REPOSITORY", repository)
    plain("AD_ANALYZER_DASHBOARD_ALLOW_INSECURE_LOCAL_HTTP", "false")
    plain("AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED", "false")
    plain("AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH", "true")
    plain("AD_ANALYZER_ALLOWED_EXECUTION_ACCOUNT_IDS", "")
    plain("AD_ANALYZER_ALLOWED_GOOGLE_ADS_MUTATIONS", "")
    plain("AD_ANALYZER_WEB_CONCURRENCY", "1")
    plain("AD_ANALYZER_WEB_TIMEOUT_SECONDS", "60")

    required_secret_names = {
        name for name in ("AD_ANALYZER_API_TOKEN", "DATABASE_PASSWORD") if name in mapped
    }
    if required_secret_names != {"AD_ANALYZER_API_TOKEN", "DATABASE_PASSWORD"}:
        raise CutoverConfigError(
            "Existing service does not expose both required web secrets through Secret Manager."
        )
    plain(
        "AD_ANALYZER_REQUIRED_SECRET_NAMES",
        "AD_ANALYZER_API_TOKEN,DATABASE_PASSWORD",
    )
    if "AD_ANALYZER_PLATFORM_ADMIN_EMAILS" not in mapped:
        raise CutoverConfigError("Existing service has no dashboard administrator allowlist.")
    if not {"CLOUD_SQL_CONNECTION_NAME", "DATABASE_USER", "DATABASE_NAME"} <= mapped.keys():
        raise CutoverConfigError("Existing service does not have complete Cloud SQL configuration.")

    return [mapped[name] for name in sorted(mapped)]


def is_source_service(service: dict[str, Any], target_service: str) -> bool:
    """Return whether a service looks like the existing Ad Analyzer web deployment."""
    names = {
        entry.get("name") for entry in _env_entries(service) if isinstance(entry.get("name"), str)
    }
    markers = (
        "IAP_AUDIENCE",
        "GOOGLE_ADS_WRITE_ENABLED",
        "GOOGLE_ADS_EXECUTION_KILL_SWITCH",
    )
    return all(any(name.endswith(f"_{marker}") for name in names) for marker in markers)


def _clean_metadata(metadata: dict[str, Any]) -> None:
    for key in SERVER_METADATA_KEYS:
        metadata.pop(key, None)
    annotations = metadata.get("annotations")
    if isinstance(annotations, dict):
        for key in list(annotations):
            if key.startswith("client.knative.dev/") or key.startswith(
                "run.googleapis.com/operation-id"
            ):
                annotations.pop(key, None)


def prepare_service(
    source: dict[str, Any],
    *,
    target_service: str,
    project_id: str,
    project_number: str,
    region: str,
    repository: str,
    image: str,
) -> dict[str, Any]:
    """Clone only the web runtime configuration and enforce the approved cost/safety profile."""
    if not is_source_service(source, target_service):
        raise CutoverConfigError("Selected source is not the existing Ad Analyzer web service.")
    service = copy.deepcopy(source)
    service.pop("status", None)
    metadata = service.setdefault("metadata", {})
    _clean_metadata(metadata)
    metadata["name"] = target_service
    # Cloud Run's v1 YAML schema expects the numeric project namespace.
    metadata["namespace"] = project_number

    template = _template(service)
    template_metadata = template.setdefault("metadata", {})
    _clean_metadata(template_metadata)
    template_metadata.pop("name", None)
    annotations = template_metadata.setdefault("annotations", {})
    annotations["autoscaling.knative.dev/minScale"] = "0"
    annotations["autoscaling.knative.dev/maxScale"] = "1"
    annotations["run.googleapis.com/cpu-throttling"] = "true"
    annotations["run.googleapis.com/startup-cpu-boost"] = "false"

    spec = _template_spec(service)
    spec["containerConcurrency"] = 80
    spec["timeoutSeconds"] = 60
    container = _container(service)
    container["image"] = image
    container["command"] = ["python"]
    container["args"] = ["scripts/cloud_run_web_start.py"]
    container["env"] = _neutral_environment(
        source,
        target_service=target_service,
        project_number=project_number,
        region=region,
        repository=repository,
    )
    resources = container.setdefault("resources", {})
    resources["limits"] = {"cpu": "1", "memory": "512Mi"}
    service["spec"]["traffic"] = [{"latestRevision": True, "percent": 100}]
    return service


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise CutoverConfigError("Cloud Run service export must be a JSON object.")
    return data


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    source_parser = subparsers.add_parser("is-source")
    source_parser.add_argument("--input", type=Path, required=True)
    source_parser.add_argument("--target-service", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--input", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--target-service", required=True)
    prepare_parser.add_argument("--project-id", required=True)
    prepare_parser.add_argument("--project-number", required=True)
    prepare_parser.add_argument("--region", required=True)
    prepare_parser.add_argument("--repository", required=True)
    prepare_parser.add_argument("--image", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    source = _load(args.input)
    if args.command == "is-source":
        return 0 if is_source_service(source, args.target_service) else 1
    prepared = prepare_service(
        source,
        target_service=args.target_service,
        project_id=args.project_id,
        project_number=args.project_number,
        region=args.region,
        repository=args.repository,
        image=args.image,
    )
    args.output.write_text(json.dumps(prepared, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
