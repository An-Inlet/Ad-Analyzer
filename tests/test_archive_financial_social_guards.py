"""Reject widened DTOs without invoking the historical producer."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.archive_financial_social_retained_fixture import (
    FILE,
    FUNCTION,
    PREFIX,
    Brand,
    SourceIds,
    read_ids,
)
from tests.retired_snapshot import PIN


def raw() -> dict[str, Any]:
    a: dict[str, Any] = {
        name: "a" * (64 if name.endswith("digest") else 32) for name in Brand.model_fields
    }
    for key in (
        "workspace_id",
        "google_account_id",
        "google_integration_id",
        "meta_connection_id",
        "meta_account_id",
        "meta_integration_id",
        "shopify_connection_id",
        "shopify_integration_id",
        "crm_connection_id",
        "crm_integration_id",
        "provider_mandate_revision",
        "source_mutation_count",
    ):
        a[key] = 1
    a.update(
        provider="meta_ads",
        google_source=dict(draft_id="b" * 32, revision=1, digest="b" * 64),
        social=dict(
            source=dict(draft_id="c" * 32, revision=1, digest="c" * 64),
            media_id="d" * 32,
            media_sha256="d" * 64,
            review_id="e" * 32,
            review_digest="e" * 64,
            approval_digest="f" * 64,
        ),
    )
    b = {
        **a,
        "provider": "google_ads",
        "workspace_id": 2,
        "actor_id": "b" * 32,
        "meta_connection_id": None,
        "meta_account_id": None,
        "meta_integration_id": None,
        "social": None,
    }
    return dict(
        schema_version="inlet.test.archive-financial-social-source.v1",
        source_commit=PIN,
        source_file_sha256=FILE,
        source_function_ast_sha256=FUNCTION,
        source_prefix_ast_sha256=PREFIX,
        brand_a=a,
        brand_b=b,
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("workspace_id", True),
        ("workspace_id", 0),
        ("workspace_id", 2147483648),
        ("source_mutation_count", True),
        ("source_mutation_count", 2),
        ("social", None),
        ("meta_account_id", None),
        ("extra", 1),
        ("original_fence", "a" * 64),
    ],
)
def test_strict_closed_brand(key: str, value: Any) -> None:
    data = raw()
    SourceIds.model_validate(data)
    data["brand_a"][key] = value
    with pytest.raises(ValidationError):
        SourceIds.model_validate(data)


@pytest.mark.parametrize(
    "kind", ["duplicate", "oversize", "symlink", "directory", "nonfinite", "valid"]
)
def test_bounded_envelope(tmp_path: Path, kind: str) -> None:
    output = tmp_path / "ids.json"
    if kind == "directory":
        output.mkdir()
    elif kind == "symlink":
        target = tmp_path / "other.json"
        target.write_text(json.dumps(raw()))
        output.symlink_to(target)
    else:
        content = json.dumps(raw())
        if kind == "duplicate":
            content = '{"schema_version":"other",' + content[1:]
        elif kind == "oversize":
            content = " " * 16385
        elif kind == "nonfinite":
            content = '{"unknown":NaN}'
        output.write_text(content)
    if kind == "valid":
        assert read_ids(output).brand_b.workspace_id == 2
    else:
        with pytest.raises((AssertionError, ValueError)):
            read_ids(output)
