import re
from pathlib import Path

GCP_TERRAFORM = Path("infra/gcp/main.tf")
SERVICE_ACCOUNT_SUFFIXES = ("gateway", "worker", "push", "api-gw")


def test_default_production_service_account_ids_are_valid_and_stable() -> None:
    account_ids = {
        "denti-prod-crm-gateway",
        "denti-prod-crm-worker",
        "denti-prod-crm-push",
        "denti-prod-crm-api-gw",
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
        'service_account_prefix = "denti-${local.service_account_environment}-crm"'
        in terraform
    )
    assert "length(account_id) >= 6 && length(account_id) <= 30" in terraform
    assert terraform.count("container_port = 8000") == 2


def test_api_config_uses_unique_prefix_before_destroying_previous_config() -> None:
    terraform = GCP_TERRAFORM.read_text()

    assert 'api_config_id_prefix = "${local.prefix}-config-"' in terraform
    assert 'api_config_id = "${local.prefix}-config"' not in terraform
    assert "lifecycle {\n    create_before_destroy = true\n  }" in terraform


def test_every_accepted_custom_environment_length_fits_service_account_limit() -> None:
    for environment_length in range(2, 13):
        environment = "e" * environment_length
        account_ids = {
            f"denti-{environment}-crm-{suffix}" for suffix in SERVICE_ACCOUNT_SUFFIXES
        }

        assert all(len(account_id) <= 30 for account_id in account_ids)

    longest_rejected_environment = "e" * 13
    assert len(f"denti-{longest_rejected_environment}-crm-gateway") > 30
