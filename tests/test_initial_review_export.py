"""Strict safe export of protected initial-preview commitments, never session authority."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.initial_planning.review_export import ReviewLinkExport
from app.lifecycle.export_serializers import exclusion, fields, serialize
from app.lifecycle.inventory import verify_registry
from app.lifecycle.registry import TABLES


def row() -> dict[str, Any]:
    now = datetime.now(UTC)
    return dict(
        review_id="a" * 32,
        workspace_id=1,
        preview_id="b" * 32,
        preview_workspace_id=1,
        preview_account_id=2,
        preview_campaign_id=3,
        actor_id="c" * 32,
        environment="contract_test",
        **{
            key: "d" * 64
            for key in (
                "preview_digest",
                "intent_digest",
                "policy_digest",
                "evidence_digest",
                "native_state_digest",
                "mandate_digest",
                "review_digest",
                "plan_digest",
            )
        },
        created_at=now,
        expires_at=now + timedelta(minutes=1),
        original_session_digest="NEVER-EXPORT-THIS-SESSION",
    )


@pytest.mark.parametrize("retracted", [False, True])
def test_protected_scalar_allowlist_and_retracted_pointer(retracted: bool) -> None:
    verify_registry()
    assert TABLES["initial_preview_reviews"].protected
    source = row()
    if retracted:
        for key in (
            "preview_id",
            "preview_workspace_id",
            "preview_account_id",
            "preview_campaign_id",
        ):
            source[key] = None
    result, missing = serialize("initial_preview_reviews", source)
    assert not missing
    assert set(result) == set(ReviewLinkExport.model_fields)
    assert set(fields("initial_preview_reviews")) == set(result)
    assert "session" not in repr(result)
    assert exclusion("initial_preview_reviews", "original_session_digest") == "security_or_internal"
    assert result["review_digest"] == source["review_digest"]
    assert result["preview_id"] == (None if retracted else source["preview_id"])


@pytest.mark.parametrize(
    "change", ["partial", "foreign", "digest", "environment", "time", "missing"]
)
def test_malformed_provenance_export_is_incomplete(change: str) -> None:
    source = row()
    if change == "partial":
        source["preview_id"] = None
    if change == "foreign":
        source["preview_workspace_id"] = 999
    if change == "digest":
        source["evidence_digest"] = "arbitrary payload"
    if change == "environment":
        source["environment"] = "unclassified"
    if change == "time":
        source["created_at"] = "untrusted string"
    if change == "missing":
        del source["mandate_digest"]
    result, missing = serialize("initial_preview_reviews", source)
    assert result == {} and set(missing) == set(fields("initial_preview_reviews"))
