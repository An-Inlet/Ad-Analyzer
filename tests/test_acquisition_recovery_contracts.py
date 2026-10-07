from datetime import UTC, date, datetime

import pytest
from app.commerce.acquisition_contracts import (
    AcquisitionRecovery,
    AcquisitionRecoveryItem,
    AcquisitionStatus,
)
from pydantic import ValidationError


def test_recovery_is_bounded_owned_metadata_without_authority() -> None:
    status = AcquisitionStatus(
        job_id="a" * 32,
        state="completed",
        phase=None,
        deadline_at=datetime(2026, 10, 7, tzinfo=UTC),
        publication_id="b" * 32,
        error_code=None,
    )
    item = AcquisitionRecoveryItem(
        status=status,
        goal_id="c" * 32,
        goal_revision=1,
        start=date(2026, 10, 1),
        end=date(2026, 10, 2),
    )
    result = AcquisitionRecovery(
        workspace_id=1, goal_id=item.goal_id, items=(item,), truncated=False
    )
    assert AcquisitionRecovery.model_validate_json(result.model_dump_json()) == result
    assert result.items[0].status.maturity == "unqualified"
    with pytest.raises(ValidationError):
        AcquisitionRecovery(workspace_id=1, goal_id="d" * 32, items=(item,), truncated=False)
    with pytest.raises(ValidationError):
        AcquisitionRecovery(
            workspace_id=1, goal_id=item.goal_id, items=(item, item), truncated=False
        )
    with pytest.raises(ValidationError):
        AcquisitionRecovery(
            workspace_id=1, goal_id=item.goal_id, items=(item,) * 21, truncated=False
        )
