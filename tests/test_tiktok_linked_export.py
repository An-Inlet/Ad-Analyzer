"""Versioned owned export of linked consent without widening historical schemas."""

from typing import Any

import pytest
from app.lifecycle.export_serializers import serialize
from app.publication.social_review_models import SocialConfigurationReview

from tests.test_commerce_measurement import NOW
from tests.test_tiktok_linked_review_contracts import document


def row() -> dict[str, Any]:
    saved = document()
    account = saved.request.account
    return dict(
        id="1" * 32,
        workspace_id=account.workspace_id,
        account_id=account.account.account_id,
        integration_id=account.account.connection_id,
        draft_id=saved.request.draft_id,
        source_revision=saved.request.draft_revision,
        digest=saved.digest(),
        document=saved.model_dump(mode="json"),
        created_by="2" * 32,
        created_at=NOW,
    )


def test_linked_configuration_export_retains_exact_version_and_commitment() -> None:
    original = row()
    exported, missing = serialize(SocialConfigurationReview.__tablename__, original)
    assert missing == []
    assert exported["document"] == original["document"]
    assert exported["digest"] == original["digest"]
    assert "access_token" not in str(exported)


@pytest.mark.parametrize(
    "field,value",
    [
        ("workspace_id", 999999),
        ("account_id", 999999),
        ("integration_id", 999999),
        ("draft_id", "a" * 32),
        ("source_revision", 999999),
        ("digest", "f" * 64),
    ],
)
def test_foreign_scalar_binding_excludes_linked_document(field: str, value: Any) -> None:
    original = row()
    assert original[field] != value
    original[field] = value
    exported, missing = serialize(SocialConfigurationReview.__tablename__, original)
    assert missing == ["document"]
    assert "document" not in exported


@pytest.mark.parametrize("change", ["unknown_schema", "rights", "extra", "foreign_identity"])
def test_invalid_linked_payload_is_not_exported_untyped(change: str) -> None:
    original = row()
    payload = original["document"]
    if change == "unknown_schema":
        payload["schema_version"] = "inlet.tiktok-linked-push-configuration-review.v2"
    elif change == "rights":
        payload["answer"]["commercial_music_rights_reviewed"] = False
    elif change == "extra":
        payload["unreviewed_raw_provider_payload"] = {"foreign": "value"}
    else:
        payload["identity_observation"]["request"]["owner"]["workspace_id"] = 999999
    exported, missing = serialize(SocialConfigurationReview.__tablename__, original)
    assert missing == ["document"]
    assert "document" not in exported
