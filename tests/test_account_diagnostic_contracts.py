from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.collectors.account_diagnostic_contracts import AccountDiagnosticIntentV1
from pydantic import ValidationError


def test_observation_intent_rejects_authority_and_unbounded_dates() -> None:
    now = datetime(2026, 10, 6, tzinfo=UTC)
    values: dict[str, Any] = dict(account_id=1, starts_at=now - timedelta(days=366), ends_at=now)
    assert AccountDiagnosticIntentV1.model_validate(values).account_id == 1
    updates: list[dict[str, Any]] = [
        dict(actor="owner"),
        dict(account_id=True),
        dict(ends_at=now + timedelta(days=1)),
    ]
    for update in updates:
        with pytest.raises(ValidationError):
            AccountDiagnosticIntentV1.model_validate({**values, **update})


def test_historical_native_request_bytes_unchanged() -> None:
    import hashlib

    from tests.test_google_native_inventory import request as google
    from tests.test_meta_native_inventory import request as meta
    from tests.test_tiktok_native_inventory import request as tiktok

    # Captured from frozen pre-extension8f384ff, not regenerated from this implementation.
    expected: list[tuple[Callable[[], Any], str, str]] = [
        (
            google,
            "f4f20697aa1a6ea86a91d9c85ca290a9beb0c3281a18410b810aaf9d031f45f6",
            "e95acb31eea365f1695f8d427ed2bc111da4dbec8bc0419e6e608765c0d58053",
        ),
        (
            meta,
            "116b981fd655dd08a0b8e03a56889579430722d6d7880f821a575d3a89450672",
            "b2925b1fad60e6b9378abc82791b672195135ca99888860922439228266417ac",
        ),
        (
            tiktok,
            "7c869eeceda37b70253802cb5ca867323fdbfc26560861386c0c42024689efb1",
            "b594e2a61eeecb89865fbcbb5f4659fde084c07702e62ce02e817cf800839e5a",
        ),
    ]
    for factory, digest, serialized in expected:
        value = factory()
        assert value.digest() == digest
        assert hashlib.sha256(value.model_dump_json().encode()).hexdigest() == serialized
