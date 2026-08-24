import re
from pathlib import Path

GCP_TERRAFORM = Path("infra/gcp/main.tf")
GCP_OUTPUTS = Path("infra/gcp/outputs.tf")
GCP_VARIABLES = Path("infra/gcp/variables.tf")
GCP_VERSIONS = Path("infra/gcp/versions.tf")
SERVICE_ACCOUNT_SUFFIXES = ("gateway", "worker", "push", "api-gw")


def test_default_production_service_account_ids_are_valid_and_stable() -> None:
    account_ids = {
        "aa-prod-crm-gateway",
        "aa-prod-crm-worker",
        "aa-prod-crm-push",
        "aa-prod-crm-api-gw",
    }

    assert len(account_ids) == 4
    assert all(6 <= len(account_id) <= 30 for account_id in account_ids)
    assert all(
        re.fullmatch(r"[a-z][a-z0-9-]*[a-z0-9]", account_id)
        for account_id in account_ids
    )


def test_terraform_guards_service_account_lengths_and_uses_application_port() -> None:
    terraform = GCP_TERRAFORM.read_text()

    assert (
        'service_account_prefix = "aa-${local.service_account_environment}-crm"'
        in terraform
    )
    assert "length(account_id) >= 6 && length(account_id) <= 30" in terraform
    assert terraform.count("container_port = 8000") == 2


def test_api_config_uses_unique_prefix_before_destroying_previous_config() -> None:
    terraform = GCP_TERRAFORM.read_text()

    assert 'api_config_id_prefix = "${local.prefix}-config-"' in terraform
    assert 'api_config_id = "${local.prefix}-config"' not in terraform
    assert "lifecycle {\n    create_before_destroy = true\n  }" in terraform


def test_api_gateway_region_is_separate_from_existing_regional_resources() -> None:
    terraform = GCP_TERRAFORM.read_text()
    variables = GCP_VARIABLES.read_text()
    gateway = _resource_body(terraform, "google_api_gateway_gateway", "crm")
    cloud_run_gateway = _resource_body(
        terraform, "google_cloud_run_v2_service", "gateway"
    )
    cloud_run_worker = _resource_body(terraform, "google_cloud_run_v2_service", "worker")

    assert re.search(r'variable "region" \{.*?default = "us-west1"', variables, re.DOTALL)
    assert re.search(
        r'variable "api_gateway_region" \{.*?default\s+= "us-west3"',
        variables,
        re.DOTALL,
    )
    assert "region     = var.api_gateway_region" in gateway
    assert "location            = var.region" in cloud_run_gateway
    assert "location            = var.region" in cloud_run_worker


def test_api_gateway_global_resources_and_deployment_names_remain_stable() -> None:
    terraform = GCP_TERRAFORM.read_text()
    api = _resource_body(terraform, "google_api_gateway_api", "crm")
    api_config = _resource_body(terraform, "google_api_gateway_api_config", "crm")
    gateway = _resource_body(terraform, "google_api_gateway_gateway", "crm")

    assert 'prefix = "ad-analyzer-${var.environment}-crm"' in terraform
    assert 'api_id   = "${local.prefix}-api"' in api
    assert 'api_config_id_prefix = "${local.prefix}-config-"' in api_config
    assert 'gateway_id = "${local.prefix}-gateway"' in gateway
    assert 'resource "google_api_gateway_api" "crm"' in terraform
    assert 'resource "google_api_gateway_api_config" "crm"' in terraform
    assert "create_before_destroy = true" in api_config
    assert terraform.count("deletion_protection = true") == 2


def test_every_accepted_custom_environment_length_fits_service_account_limit() -> None:
    for environment_length in range(2, 13):
        environment = "e" * environment_length
        account_ids = {
            f"aa-{environment}-crm-{suffix}" for suffix in SERVICE_ACCOUNT_SUFFIXES
        }

        assert all(len(account_id) <= 30 for account_id in account_ids)



def _resource_body(terraform: str, resource_type: str, name: str) -> str:
    start = terraform.index(f'resource "{resource_type}" "{name}"')
    next_block = terraform.find('\nresource "', start + 1)
    return terraform[start : next_block if next_block != -1 else None]


def test_worker_uses_existing_database_password_secret() -> None:
    terraform = GCP_TERRAFORM.read_text()
    variables = GCP_VARIABLES.read_text()

    assert 'resource "google_secret_manager_secret" "database"' not in terraform + variables
    assert 'data "google_secret_manager_secret" "database_password"' in terraform
    assert "secret_id = var.database_password_secret_id" in terraform
    assert 'variable "database_password_secret_id"' in variables
    assert 'default = "DATABASE_PASSWORD"' in variables
    assert "var.database_secret_id" not in terraform + variables


def test_remote_state_and_existing_webhook_secret_are_declarative_only() -> None:
    terraform = GCP_TERRAFORM.read_text()
    variables = GCP_VARIABLES.read_text()
    all_terraform = "".join(path.read_text() for path in Path("infra/gcp").glob("*.tf"))

    assert 'backend "gcs" {}' in GCP_VERSIONS.read_text()
    assert 'resource "google_secret_manager_secret" "webhook"' not in terraform
    assert 'data "google_secret_manager_secret" "webhook"' in terraform
    assert "secret_id = var.webhook_secret_id" in terraform
    webhook_variable = re.search(
        r'variable "webhook_secret_id" \{(?P<body>.*?)\n\}',
        variables,
        re.DOTALL,
    )
    assert webhook_variable is not None
    assert "description =" in webhook_variable.group("body")
    assert "default =" not in webhook_variable.group("body")
    assert "google_secret_manager_secret_version" not in all_terraform
    assert (
        "data.google_secret_manager_secret.webhook.secret_id"
        in GCP_OUTPUTS.read_text()
    )


def test_gateway_uses_existing_webhook_secret_for_injection_and_iam() -> None:
    terraform = GCP_TERRAFORM.read_text()
    gateway = _resource_body(terraform, "google_cloud_run_v2_service", "gateway")
    webhook_iam = _resource_body(
        terraform, "google_secret_manager_secret_iam_member", "gateway_webhook"
    )

    assert 'name = "AD_ANALYZER_CRM_WEBHOOK_SECRET"' in gateway
    assert "data.google_secret_manager_secret.webhook.secret_id" in gateway
    assert "secret_id = data.google_secret_manager_secret.webhook.id" in webhook_iam


def test_worker_has_cloud_sql_socket_configuration_and_database_environment() -> None:
    terraform = GCP_TERRAFORM.read_text()
    worker = _resource_body(terraform, "google_cloud_run_v2_service", "worker")

    assert 'cloud_sql_instance {' in worker
    assert "instances = [var.cloud_sql_connection_name]" in worker
    assert 'mount_path = "/cloudsql"' in worker
    for name in (
        "CLOUD_SQL_CONNECTION_NAME",
        "DATABASE_USER",
        "DATABASE_NAME",
        "DATABASE_PASSWORD",
    ):
        assert f'name  = "{name}"' in worker or f'name = "{name}"' in worker
    assert 'name  = "AD_ANALYZER_REQUIRED_SECRET_NAMES"' in worker
    assert 'value = "DATABASE_PASSWORD"' in worker
    assert "data.google_secret_manager_secret.database_password.secret_id" in worker
    assert 'version = "latest"' in worker


def test_cloud_sql_access_is_worker_only_and_gateway_has_no_database_configuration() -> None:
    terraform = GCP_TERRAFORM.read_text()
    gateway = _resource_body(terraform, "google_cloud_run_v2_service", "gateway")
    cloud_sql_iam = _resource_body(
        terraform, "google_project_iam_member", "worker_cloud_sql_client"
    )

    assert terraform.count('role    = "roles/cloudsql.client"') == 1
    assert "google_service_account.worker.email" in cloud_sql_iam
    assert "cloud_sql" not in gateway.lower()
    assert "DATABASE_" not in gateway


def test_cloud_run_services_wait_for_their_secret_and_database_iam() -> None:
    terraform = GCP_TERRAFORM.read_text()
    gateway = _resource_body(terraform, "google_cloud_run_v2_service", "gateway")
    worker = _resource_body(terraform, "google_cloud_run_v2_service", "worker")

    assert "depends_on = [" in gateway
    assert "google_project_service.required," in gateway
    assert "google_secret_manager_secret_iam_member.gateway_webhook," in gateway

    assert "depends_on = [" in worker
    assert "google_project_service.required," in worker
    assert "google_secret_manager_secret_iam_member.worker_database," in worker
    assert "google_project_iam_member.worker_cloud_sql_client," in worker


def test_sql_admin_api_is_enabled() -> None:
    assert '"sqladmin.googleapis.com"' in GCP_TERRAFORM.read_text()
