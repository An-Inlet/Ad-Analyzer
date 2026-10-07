"""Explicit linked pins/intent; no legacy bundle or identity promotion."""

import json
from pathlib import Path
from typing import Any

import pytest
from app.production_runtime.tiktok_configuration import (
    TikTokConfigurationBundleV1,
    TikTokRuntimeConfigurationError,
    load_tiktok_execution_configuration,
)
from app.production_runtime.tiktok_linked_configuration import TikTokLinkedConfigurationBundleV1
from app.publication.tiktok_linked_customer_contracts import LinkedPushReviewIntent
from pydantic import ValidationError

from tests.test_tiktok_runtime_contracts import bundle_document, manifest


def linked_bundle() -> TikTokLinkedConfigurationBundleV1:
    value = bundle_document()
    del value["cover_review_required"]
    value.update(identity_type="TT_USER", dark_post_status="ON")
    return TikTokLinkedConfigurationBundleV1.from_document(value)


def test_explicit_linked_loader_preserves_old_bundle_bytes(tmp_path: Path) -> None:
    legacy = TikTokConfigurationBundleV1.from_document(bundle_document())
    old_digest = legacy.digest()
    linked = linked_bundle()
    descriptor = manifest(legacy).model_copy(
        update={"configuration_bundle_digest": linked.digest()}
    )
    path, rules = tmp_path / "manifest.json", tmp_path / "bundle.json"
    path.write_text(descriptor.model_dump_json())
    rules.write_bytes(linked._canonical)
    loaded = load_tiktok_execution_configuration(str(path), descriptor.digest(), str(rules))
    assert loaded is not None and isinstance(loaded[1], TikTokLinkedConfigurationBundleV1)
    assert legacy.digest() == old_digest and old_digest != linked.digest()
    loaded[1].profiles[0].language_codes["en"] = "altered"
    assert loaded[1].digest() == linked.digest()
    rules.write_text(json.dumps(bundle_document()))
    with pytest.raises(TikTokRuntimeConfigurationError):
        load_tiktok_execution_configuration(str(path), descriptor.digest(), str(rules))


def test_customer_intent_rejects_provider_proofs_and_unreviewed_answer() -> None:
    value: dict[str, Any] = dict(
        draft_id="a" * 32,
        draft_revision=1,
        option_id="b" * 64,
        cover_media_id="c" * 32,
        answer=dict(
            kind="tiktok_linked_push",
            reviewed_video_and_cover=True,
            commercial_music_rights_reviewed=True,
            creates_new_linked_post_reviewed=True,
            ads_only_visibility_reviewed=True,
        ),
    )
    assert LinkedPushReviewIntent.model_validate(value).draft_revision == 1
    changes_list: tuple[dict[str, Any], ...] = (
        {"identity_id": "native"},
        {"provider_proof": {}},
        {"answer": {**value["answer"], "commercial_music_rights_reviewed": 1}},
    )
    for changes in changes_list:
        with pytest.raises(ValidationError):
            LinkedPushReviewIntent.model_validate({**value, **changes})
