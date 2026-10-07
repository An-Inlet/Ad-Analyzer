from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.commerce.acquisition_contracts import (
    AcquisitionIntent,
    AcquisitionProfile,
    NativeHandles,
    initial_checkpoint,
)
from app.commerce.acquisition_handles import open_handles, seal_handles
from app.commerce.independent_contracts import ScanLimits, ScanUnavailable
from app.settings import Settings
from app.shopify.security import Vault
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError

from tests.test_independent_acquisition_contracts import request


def profile(**changes: Any) -> AcquisitionProfile:
    return AcquisitionProfile.model_validate(
        {
            "limits": ScanLimits(),
            "poll_interval_seconds": 10,
            "tick_time_budget_seconds": 10,
            "tick_request_budget": 100,
            "tick_workspace_budget": 20,
            "step_io_timeout_seconds": 2,
            "lease_seconds": 15,
            "backoff_seconds": 30,
            "seen_key_limit": 100_000,
            **changes,
        }
    )


def test_customer_intent_cannot_supply_query_or_source_proof() -> None:
    scan = request()
    value = dict(
        goal_id=scan.scope.goal_id, expected_goal_revision=1, start=scan.start, end=scan.end
    )
    AcquisitionIntent.model_validate(value)
    for field in ("query", "cursor", "credentials", "scope", "clock", "maturity"):
        with pytest.raises(ValidationError):
            AcquisitionIntent.model_validate({**value, field: "injected"})


@pytest.mark.parametrize(
    "changes",
    [
        {"poll_interval_seconds": 3600},
        {"limits": ScanLimits(lifetime_seconds=60)},
        {"step_io_timeout_seconds": 5, "tick_time_budget_seconds": 1},
    ],
)
def test_unworkable_cadence_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        profile(**changes)


@pytest.mark.parametrize(
    "drift", ["workspace", "store", "job", "request", "phase", "sequence", "state"]
)
def test_handles_bound_to_exact_owned_checkpoint(drift: str) -> None:
    scan = request()
    checkpoint = initial_checkpoint(scan, profile())
    vault = Vault(
        Settings(
            shopify_token_encryption_key=SecretStr(Fernet.generate_key().decode()),
            shopify_identifier_hash_key=SecretStr("k" * 32),
        )
    )
    handles = NativeHandles(
        order_ids=("gid://shopify/Order/9",),
        last_order_number="9",
        order_cursor=None,
        agreement_cursor=None,
        sale_cursor=None,
        agreement_id=None,
    )
    now = datetime(2026, 10, 3, tzinfo=UTC)
    deadline = now + timedelta(minutes=30)
    encrypted = seal_handles(vault, scan, checkpoint, handles, deadline_at=deadline)
    assert "gid://" not in encrypted
    with pytest.raises(ScanUnavailable, match="acquisition_expired"):
        open_handles(vault, scan, checkpoint, encrypted, deadline_at=deadline, now=deadline)
    assert (
        open_handles(vault, scan, checkpoint, encrypted, deadline_at=deadline, now=now) == handles
    )
    if drift in {"workspace", "store"}:
        scope = scan.scope.model_copy(
            update={
                "workspace_id" if drift == "workspace" else "store_id": 2
                if drift == "workspace"
                else "f" * 32,
            }
        )
        scan = scan.model_copy(update={"scope": scope})
        checkpoint = checkpoint.model_copy(update={"request_digest": scan.request_digest})
    elif drift in {"job", "request"}:
        scan = scan.model_copy(
            update={
                "acquisition_id" if drift == "job" else "connection_version": "f" * 32,
            }
        )
        checkpoint = checkpoint.model_copy(update={"request_digest": scan.request_digest})
    else:
        checkpoint = checkpoint.model_copy(
            update={
                {"phase": "phase", "sequence": "sequence", "state": "orders_more"}[drift]: {
                    "phase": "order_page",
                    "sequence": 1,
                    "state": True,
                }[drift],
            }
        )
    with pytest.raises(ScanUnavailable, match="acquisition_checkpoint_invalid"):
        open_handles(vault, scan, checkpoint, encrypted, deadline_at=deadline, now=now)


def test_native_handles_have_no_customer_or_payload_slot() -> None:
    with pytest.raises(ValidationError):
        NativeHandles.model_validate(
            dict(
                order_ids=(),
                last_order_number="0",
                order_cursor=None,
                agreement_cursor=None,
                sale_cursor=None,
                agreement_id=None,
                customer_id="gid://shopify/Customer/2",
            )
        )
    frozen = initial_checkpoint(request(), profile())
    with pytest.raises(ValidationError):
        frozen.sequence = 1  # type: ignore[misc]
