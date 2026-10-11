"""Standalone pure contracts; fixture witnesses confer no authenticated ownership."""

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from app.campaign_review.contracts import MAX_IMAGE_BYTES, MAX_LIBRARY_BYTES, MAX_PIXELS
from app.planning_documents.creative_basis import (
    CreativeBasisV1,
    CreativeInputV1,
    CustomerListPriceV1,
    CustomerProductV1,
    OwnedPlanningImageV1,
    PlanningMediaSelectionV1,
)
from pydantic import ValidationError


def image(n: int = 1) -> OwnedPlanningImageV1:
    return OwnedPlanningImageV1(
        workspace_id=1,
        media_id=f"{n:032x}",
        sha256=f"{n:064x}",
        size=MAX_IMAGE_BYTES,
        mime="image/png",
        width=4000,
        height=4000,
        created_at="2026-10-01T12:00:00-04:00",
        observed_at="2026-10-02T16:00:00Z",
        privacy_revision=0,
    )


def basis(count: int = 1) -> CreativeBasisV1:
    images = tuple(image(n) for n in range(1, count + 1))
    return CreativeBasisV1(
        workspace_id=1,
        goal_currency="USD",
        privacy_revision=0,
        requested=CreativeInputV1(
            product=CustomerProductV1(
                name="Reusable travel mug",
                list_price=CustomerListPriceV1(micros=25_000_000, currency="USD"),
                customer_asserted_facts=("Reusable",),
                restrictions=("No approved health claims or testimonials",),
            ),
            media_selections=tuple(
                PlanningMediaSelectionV1(media_id=x.media_id, expected_sha256=x.sha256)
                for x in images
            ),
        ),
        images=images,
    )


def test_deterministic_roundtrip_tags_and_no_authority() -> None:
    value = basis()
    assert CreativeBasisV1.model_validate_json(value.model_dump_json()) == value
    assert value.digest() == CreativeBasisV1.model_validate_json(value.model_dump_json()).digest()
    assert value.images[0].created_at == datetime(2026, 10, 1, 16, tzinfo=UTC)
    assert value.images[0].visual_assessment == "not_assessed"
    for obj in (
        value,
        value.requested,
        value.requested.product,
        value.images[0],
        value.requested.media_selections[0],
    ):
        assert obj is not None
        assert not obj.advertising_writes_enabled and obj.spending_authority == "none"
        assert obj.schema_version.startswith("inlet.")
    assert basis(0).images == ()
    assert basis(2).digest() != value.digest()


@pytest.mark.parametrize(
    "change",
    [
        {"workspace_id": True},
        {"privacy_revision": "0"},
        {"size": 0},
        {"size": MAX_IMAGE_BYTES + 1},
        {"size": 1.0},
        {"width": True},
        {"height": 0},
        {"width": MAX_PIXELS + 1, "height": 1},
        {"media_id": b"1" * 32},
        {"sha256": b"1" * 64},
        {"mime": "video/mp4"},
        {"mime": "image/webp"},
        {"visual_assessment": "suitable"},
        {"advertising_writes_enabled": True},
        {"advertising_writes_enabled": 0},
        {"spending_authority": "approved"},
        {"url": "https://example.invalid/image"},
    ],
)
def test_strict_image_copied_instances(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        OwnedPlanningImageV1.model_validate(image().model_copy(update=change))


@pytest.mark.parametrize(
    "value",
    [True, 0, 1.0, "12345678", b"2026-10-01T12:00:00Z", "2026-10-01", datetime(2026, 10, 1)],
)
def test_timestamp_coercion_rejected(value: Any) -> None:
    with pytest.raises(ValidationError):
        OwnedPlanningImageV1.model_validate(image().model_copy(update={"observed_at": value}))


def test_dst_fold_uses_instant_order_and_equivalent_offsets_digest() -> None:
    zone = ZoneInfo("America/New_York")
    first = datetime(2026, 11, 1, 1, 45, tzinfo=zone, fold=0)
    second = datetime(2026, 11, 1, 1, 15, tzinfo=zone, fold=1)
    raw = image().model_copy(update={"created_at": first, "observed_at": second})
    valid = OwnedPlanningImageV1.model_validate(raw)
    assert valid.created_at < valid.observed_at
    alternate = OwnedPlanningImageV1.model_validate(
        raw.model_copy(
            update={"created_at": first.astimezone(UTC), "observed_at": second.astimezone(UTC)}
        )
    )
    assert valid.digest() == alternate.digest()
    with pytest.raises(ValidationError):
        OwnedPlanningImageV1.model_validate(
            raw.model_copy(update={"created_at": second, "observed_at": first})
        )


@pytest.mark.parametrize(
    "change",
    [
        "workspace",
        "privacy",
        "digest",
        "missing",
        "order",
        "currency",
        "nested_price",
        "nested_image",
    ],
)
def test_exact_basis_revalidates_nested_copies(change: str) -> None:
    value = basis(2)
    if change in {"workspace", "privacy", "digest", "nested_image"}:
        field, changed = {
            "workspace": ("workspace_id", 2),
            "privacy": ("privacy_revision", 1),
            "digest": ("sha256", "f" * 64),
            "nested_image": ("size", True),
        }[change]
        value = value.model_copy(
            update={
                "images": (value.images[0].model_copy(update={field: changed}), value.images[1])
            }
        )
    elif change == "missing":
        value = value.model_copy(update={"images": value.images[:1]})
    elif change == "order":
        value = value.model_copy(update={"images": tuple(reversed(value.images))})
    else:
        product = value.requested.product
        assert product is not None and product.list_price is not None
        price = product.list_price.model_copy(
            update={"currency": "EUR"} if change == "currency" else {"micros": True}
        )
        value = value.model_copy(
            update={
                "requested": value.requested.model_copy(
                    update={"product": product.model_copy(update={"list_price": price})}
                )
            }
        )
    with pytest.raises(ValidationError):
        CreativeBasisV1.model_validate(value)
    with pytest.raises(ValidationError):
        value.digest()


def test_duplicate_selection_order_and_library_capacity() -> None:
    original = basis(2)
    item = original.requested.media_selections[0]
    for other in (item, item.model_copy(update={"expected_sha256": "f" * 64})):
        with pytest.raises(ValidationError):
            CreativeInputV1(media_selections=(item, other))
    assert sum(x.size for x in basis(16).images) == MAX_LIBRARY_BYTES
    with pytest.raises(ValidationError, match="library"):
        basis(17)
    reverse = original.model_copy(
        update={
            "images": tuple(reversed(original.images)),
            "requested": original.requested.model_copy(
                update={"media_selections": tuple(reversed(original.requested.media_selections))}
            ),
        }
    )
    assert CreativeBasisV1.model_validate(reverse).digest() != original.digest()
    with pytest.raises(ValidationError):
        CreativeInputV1.model_validate({"media_selections": set()})
    with pytest.raises(ValidationError):
        CreativeInputV1(media_selections=(item,) * 31)


@pytest.mark.parametrize(
    "change",
    [
        {"name": b"Mug"},
        {"name": "x" * 161},
        {"customer_asserted_facts": ("a",) * 21},
        {"restrictions": ("x" * 2001,)},
        {"provenance": "verified"},
        {"claim_review": "approved"},
    ],
)
def test_product_bounds(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CustomerProductV1.model_validate({"name": "Mug", **change})


@pytest.mark.parametrize("extra", ["workspace_id", "path", "url", "mime", "width", "ownership"])
def test_client_media_selection_cannot_assert_server_metadata(extra: str) -> None:
    with pytest.raises(ValidationError):
        PlanningMediaSelectionV1.model_validate(
            {"media_id": "1" * 32, "expected_sha256": "2" * 64, extra: 1}
        )


@pytest.mark.parametrize("micros", [-1, True, 25.0, "25000000", 10**15 + 1])
def test_price_is_bounded_integer_micros(micros: Any) -> None:
    with pytest.raises(ValidationError):
        CustomerListPriceV1(micros=micros, currency="USD")


def test_zero_price_and_exact_schema_tags() -> None:
    assert CustomerListPriceV1(micros=0, currency="USD").micros == 0
    value = basis()
    for obj in (
        value,
        value.requested,
        value.requested.product,
        value.images[0],
        value.requested.media_selections[0],
    ):
        assert obj is not None
        with pytest.raises(ValidationError):
            type(obj).model_validate(obj.model_copy(update={"schema_version": "inlet.other.v1"}))
