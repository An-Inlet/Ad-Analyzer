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
    assert "run.googleapis.com/iap-enabled" in workflow
    assert "value(iapEnabled)" not in workflow
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
    assert "gcloud run jobs create" not in workflow
    assert "python scripts/prepare_release_job.py" in workflow
    assert 'gcloud run jobs execute "$job"' in workflow
    assert workflow.index("gcloud run jobs execute") < workflow.index("gcloud run services replace")


def test_cutover_request_matches_the_approved_target() -> None:
    request = json.loads(Path("deploy/ad-analyzer-web-cutover-request.json").read_text())
    assert request["target_service"] == "ad-analyzer-web"
    assert "min 0, max 1" in request["approved_cost_profile"]


def test_routine_release_preserves_current_service_configuration() -> None:
    module = load_script()
    source = source_service()
    source["metadata"]["name"] = "ad-analyzer-web"
    source["spec"]["template"]["metadata"]["name"] = "old-revision"
    source["spec"]["template"]["spec"]["containers"][0]["env"].append(
        {"name": "AD_ANALYZER_SHOPIFY_ENABLED", "value": "false"}
    )
    prepared = module.prepare_service(
        source,
        target_service="ad-analyzer-web",
        project_id="project",
        project_number="123",
        region="us-west1",
        repository="owner/repository",
        image="registry/project/repo/ad-analyzer-web:new",
    )
    template = prepared["spec"]["template"]
    assert "name" not in template["metadata"]
    assert {"name": "AD_ANALYZER_SHOPIFY_ENABLED", "value": "false"} in template["spec"][
        "containers"
    ][0]["env"]
    assert source["spec"]["template"]["metadata"]["name"] == "old-revision"


@pytest.mark.parametrize("disabled", [True, False])
def test_hourly_worker_runs_independent_tick_when_ads_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
    disabled: bool,
) -> None:
    from types import SimpleNamespace

    from app.ads.enums import JobRunStatus
    from app.jobs import google_ads_scheduler, google_ads_sync_once

    called: list[object] = []
    runtime_engine = object()
    monkeypatch.setattr(
        google_ads_scheduler,
        "_run_analysis_tick",
        lambda engine, outcome: called.append(engine),
    )
    outcome = SimpleNamespace(skipped=True, skip_reason="disabled" if disabled else "overlap")
    result = google_ads_sync_once.main(
        lambda: (object(), runtime_engine, lambda *a, **kw: outcome, JobRunStatus)
    )
    assert called == [runtime_engine]
    assert result == (0 if disabled else 2)


@pytest.mark.parametrize(
    ("command", "database_name", "expected"),
    [
        (["python", "-m", "app.jobs.google_ads_sync_once"], "existing_db", "sync"),
        (["sh", "-c", "alembic upgrade head"], "existing_db", "migration"),
        (["python", "-m", "app.jobs.google_ads_sync_once"], "another_db", None),
        (["python", "unrelated.py"], "existing_db", None),
    ],
)
def test_release_jobs_require_matching_database_and_entrypoint(
    command: list[str],
    database_name: str,
    expected: str | None,
) -> None:
    import copy

    spec = importlib.util.spec_from_file_location(
        "select_release_jobs", "scripts/select_release_jobs.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = source_service()
    container = copy.deepcopy(source["spec"]["template"]["spec"]["containers"][0])
    container["command"] = command
    for item in container["env"]:
        if item["name"] == "DATABASE_NAME":
            item["value"] = database_name
    job = {"spec": {"template": {"spec": {"template": {"spec": {"containers": [container]}}}}}}
    assert module.select_role(job, source) == expected


def test_release_job_normalizes_legacy_names_without_exposing_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend("scripts")
    prepare_release_job = __import__("prepare_release_job")

    source = source_service()
    job = {
        "metadata": {"name": "existing-job"},
        "spec": {"template": {"spec": {"template": source["spec"]["template"]}}},
    }
    prepared = prepare_release_job.prepare_job(job, "registry/new:sha")
    container = prepared["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]
    env = {item["name"]: item for item in container["env"]}
    assert "valueFrom" in env["AD_ANALYZER_API_TOKEN"]
    assert env["AD_ANALYZER_REQUIRED_SECRET_NAMES"]["value"] == "DATABASE_PASSWORD"
    assert container["image"] == "registry/new:sha"
    assert container["env"] != source["spec"]["template"]["spec"]["containers"][0]["env"]


def test_release_diagnostics_only_emit_allowlisted_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend("scripts")
    summarize_release_failure = __import__("summarize_release_failure")

    assert summarize_release_failure.summarize(
        [
            {"textPayload": "private payload required_secrets: failed private identifiers"},
            {"textPayload": "OperationalError confidential database URL"},
        ]
    ) == ["OperationalError", "required_secrets: failed"]
