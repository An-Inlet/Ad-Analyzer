import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path("scripts/prepare_cloud_run_cutover.py")
WORKFLOW = Path(".github/workflows/deploy-ad-analyzer-web.yml")


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("prepare_cloud_run_cutover", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def legacy_name(suffix: str) -> str:
    return "DENTI" + "CODE_" + suffix


def source_service(*, plaintext_api_token: bool = False) -> dict[str, Any]:
    api_token: dict[str, Any] = {
        "name": legacy_name("API_TOKEN"),
        "valueFrom": {"secretKeyRef": {"name": "platform-api-token", "key": "latest"}},
    }
    if plaintext_api_token:
        api_token = {"name": legacy_name("API_TOKEN"), "value": "unsafe-value"}
    env = [
        {"name": "APP_ENV", "value": "production"},
        {"name": "CLOUD_SQL_CONNECTION_NAME", "value": "project:region:existing-db"},
        {"name": "DATABASE_USER", "value": "existing_app"},
        {"name": "DATABASE_NAME", "value": "existing_db"},
        {
            "name": "DATABASE_PASSWORD",
            "valueFrom": {"secretKeyRef": {"name": "database-password", "key": "latest"}},
        },
        api_token,
        {"name": legacy_name("IAP_AUDIENCE"), "value": "/old/audience"},
        {"name": legacy_name("DASHBOARD_ALLOWED_EMAILS"), "value": "owner@example.com"},
        {"name": legacy_name("GOOGLE_ADS_WRITE_ENABLED"), "value": "false"},
        {"name": legacy_name("GOOGLE_ADS_EXECUTION_KILL_SWITCH"), "value": "true"},
        {"name": legacy_name("REQUIRED_SECRET_NAMES"), "value": "DATABASE_PASSWORD"},
    ]
    return {
        "apiVersion": "serving.knative.dev/v1",
        "kind": "Service",
        "metadata": {
            "name": "existing-web",
            "namespace": "project",
            "resourceVersion": "discard-me",
        },
        "spec": {
            "template": {
                "metadata": {"annotations": {"autoscaling.knative.dev/maxScale": "4"}},
                "spec": {
                    "serviceAccountName": "existing-runtime@example.invalid",
                    "containers": [{"image": "registry/project/repo/old:tag", "env": env}],
                },
            },
            "traffic": [{"revisionName": "old", "percent": 100}],
        },
        "status": {"url": "https://old.invalid"},
    }


def test_prepare_service_reuses_resources_and_caps_cost() -> None:
    module = load_script()
    prepared = module.prepare_service(
        source_service(),
        target_service="ad-analyzer-web",
        project_id="project",
        project_number="123",
        region="us-west1",
        repository="owner/repository",
        image="registry/project/repo/ad-analyzer-web:sha",
    )
    assert "status" not in prepared
    assert "resourceVersion" not in prepared["metadata"]
    assert prepared["metadata"]["name"] == "ad-analyzer-web"
    assert prepared["metadata"]["namespace"] == "123"
    template = prepared["spec"]["template"]
    assert template["metadata"]["annotations"]["autoscaling.knative.dev/minScale"] == "0"
    assert template["metadata"]["annotations"]["autoscaling.knative.dev/maxScale"] == "1"
    container = template["spec"]["containers"][0]
    assert container["image"].endswith("/ad-analyzer-web:sha")
    assert container["command"] == ["python"]
    assert container["args"] == ["scripts/cloud_run_web_start.py"]
    env = {entry["name"]: entry for entry in container["env"]}
    assert env["AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED"]["value"] == "false"
    assert env["AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH"]["value"] == "true"
    assert env["AD_ANALYZER_ALLOWED_EXECUTION_ACCOUNT_IDS"]["value"] == ""
    assert env["AD_ANALYZER_ALLOWED_GOOGLE_ADS_MUTATIONS"]["value"] == ""
    assert env["AD_ANALYZER_IAP_AUDIENCE"]["value"].endswith("/services/ad-analyzer-web")
    assert "valueFrom" in env["AD_ANALYZER_API_TOKEN"]
    assert "valueFrom" in env["DATABASE_PASSWORD"]
    assert not any(name.startswith(legacy_name("")) for name in env)


def test_prepare_service_rejects_plaintext_secrets() -> None:
    module = load_script()
    with pytest.raises(module.CutoverConfigError, match="Secret Manager-backed"):
        module.prepare_service(
            source_service(plaintext_api_token=True),
            target_service="ad-analyzer-web",
            project_id="project",
            project_number="123",
            region="us-west1",
            repository="owner/repository",
            image="registry/project/repo/ad-analyzer-web:sha",
        )


def test_workflow_is_one_time_cost_guarded_and_keyless() -> None:
    workflow = WORKFLOW.read_text()
    assert "schedule:" not in workflow
    assert "deploy/ad-analyzer-web-cutover-request.json" in workflow
    assert "--min=0" in workflow
    assert "--max=1" in workflow
    assert "--cpu-throttling" in workflow
    assert "--no-cpu-boost" in workflow
    assert "--iap" in workflow
    assert "--invoker-iam-check" in workflow
    assert "google-github-actions/auth@v3" in workflow
    assert "providers/ad-analyzer-operations" in workflow
    assert "ad-analyzer-github-ops@" in workflow
    assert "vars.GCP_WORKLOAD_IDENTITY_PROVIDER" in workflow
    assert "vars.GCP_OPERATIONS_SERVICE_ACCOUNT" in workflow
    assert "neutral Workload Identity provider variable is missing or malformed" in workflow
    assert "different Google Cloud project" in workflow
    assert "GCP_PROJECT_NUMBER: '89443799388'" not in workflow
    assert "gcloud projects describe" in workflow
    assert "needs.preflight.outputs.project_number" in workflow
    assert "service-account-key" not in workflow.lower()
    assert "gcloud sql instances create" not in workflow
    assert "gcloud scheduler" not in workflow
    assert "gcloud run jobs" not in workflow


def test_cutover_request_matches_the_approved_target() -> None:
    request = json.loads(Path("deploy/ad-analyzer-web-cutover-request.json").read_text())
    assert request["target_service"] == "ad-analyzer-web"
    assert "min 0, max 1" in request["approved_cost_profile"]
