"""Frozen legacy evidence is not reinterpreted by the new metadata sidecar."""

from pathlib import Path

import pytest
from app.collectors.google_native_inventory import GoogleNativeInventory
from app.collectors.meta_native_inventory import MetaNativeInventory
from app.collectors.tiktok_native_inventory import TikTokNativeInventory
from app.planning_catalog.metadata_contracts import MetadataEntityV1, ProviderReferenceV1
from pydantic import ValidationError


@pytest.mark.parametrize(
    "name,model",
    [
        ("google", GoogleNativeInventory),
        ("meta", MetaNativeInventory),
        ("tiktok", TikTokNativeInventory),
    ],
)
def test_legacy_observation_bytes_and_hash(
    name: str,
    model: type[GoogleNativeInventory] | type[MetaNativeInventory] | type[TikTokNativeInventory],
) -> None:
    path = Path(__file__).parent / "fixtures" / "planning_catalog_legacy"
    raw = (path / f"{name}.json").read_text()
    result = model.model_validate_json(raw)
    assert result.model_dump_json() == raw
    assert result.digest() == (path / f"{name}.sha256").read_text().strip()


def test_metadata_name_provenance_and_nested_reference_revalidation() -> None:
    reference = ProviderReferenceV1(
        platform="google_ads", advertiser_id="1234567890", entity_id="1", parent_campaign_id=None
    )
    value = dict(
        kind="campaign",
        reference=reference,
        name="<script>literal</script>",
        name_status="observed",
        status=None,
        entity_type=None,
    )
    assert MetadataEntityV1.model_validate(value).name == "<script>literal</script>"
    changes: list[dict[str, object]] = [
        dict(name="x" * 161),
        dict(name=None),
        dict(reference=reference.model_copy(update={"advertiser_id": "foreign"})),
    ]
    for changed in changes:
        with pytest.raises(ValidationError):
            MetadataEntityV1.model_validate({**value, **changed})
