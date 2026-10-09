"""Strict scalar-only original lock-source boundary, validated without database IO."""

from typing import Any

import pytest
from pydantic import ValidationError

from tests.meta_review_lock_retained_fixture import MetaLockIds


def valid() -> dict[str, Any]:
    return dict(
        workspace_id=1, mandate_id="a" * 32, mandate_revision=1,
        account_id=2, integration_id=3, native_id=4,
    )


@pytest.mark.parametrize("field", [
    "workspace_id", "mandate_revision", "account_id", "integration_id", "native_id",
])
@pytest.mark.parametrize("bad", [True, 0, "1"])
def test_source_integer_ids_are_strict(field: str, bad: Any) -> None:
    with pytest.raises(ValidationError):
        MetaLockIds.model_validate({**valid(), field: bad})


@pytest.mark.parametrize("bad", ["a" * 31, "g" * 32])
def test_source_uuid_is_exact(bad: str) -> None:
    with pytest.raises(ValidationError):
        MetaLockIds.model_validate({**valid(), "mandate_id": bad})


def test_source_has_no_open_runtime_or_authority_field() -> None:
    with pytest.raises(ValidationError):
        MetaLockIds.model_validate({**valid(), "runtime": {}})
    assert MetaLockIds.model_validate(valid()).model_dump() == valid()
