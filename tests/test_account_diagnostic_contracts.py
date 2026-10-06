from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.collectors.account_diagnostic_contracts import AccountDiagnosticIntentV1


def test_observation_intent_rejects_authority_and_unbounded_dates():
    now = datetime(2026, 10, 6, tzinfo=UTC)
    values = dict(account_id=1, starts_at=now - timedelta(days=366), ends_at=now)
    assert AccountDiagnosticIntentV1(**values).account_id == 1
    for update in [dict(actor="owner"), dict(account_id=True), dict(ends_at=now + timedelta(days=1))]:
        with pytest.raises(ValidationError):
            AccountDiagnosticIntentV1.model_validate({**values, **update})
