"""Restriction-only context entry, no SQL authority or timing qualification."""

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from app.planning_documents.creative_retained_sources import _Context
from app.planning_documents.google_budget_owner_retained import (
    capture_owner_review_retained_sources,
    recheck_owner_review_retained_sources,
)
from app.planning_documents.owner_review_policy import (
    OWNER_REVIEW_GENERATOR_VERSION,
    OWNER_REVIEW_POLICY_VERSION,
)

from tests.owner_review_v6_fixture import ready as owner_ready
from tests.test_creative_plan_composer import compose, ready
from tests.test_owner_review_v6_pure import compose as owner_compose

PAIR = (OWNER_REVIEW_POLICY_VERSION, OWNER_REVIEW_GENERATOR_VERSION)


class NoAccess:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError("policy/model validation must precede database and principal access")


@pytest.mark.parametrize(
    "restriction",
    [
        (),
        ("only",),
        ["a", "b"],
        ("a", True),
        (b"a", "b"),
        ("inlet.descriptive-review.v7", "inlet.descriptive-planning.v7"),
    ],
)
def test_invalid_or_nonmatching_restriction_cannot_touch_sql(restriction: Any) -> None:
    document = owner_compose(owner_ready())
    with pytest.raises(ValueError, match="exact owner review document required"):
        _Context(
            cast(Any, NoAccess()),
            cast(Any, NoAccess()),
            document,
            datetime.now(UTC),
            required_pair=restriction,
        )


@pytest.mark.parametrize("operation", ["capture", "recheck"])
def test_owner_wrong_pair_refuses_even_before_invalid_now(operation: str) -> None:
    document = compose(ready())
    with pytest.raises(ValueError, match="exact owner review document required"):
        if operation == "capture":
            capture_owner_review_retained_sources(
                cast(Any, NoAccess()),
                principal=cast(Any, NoAccess()),
                document=document,
                now=cast(Any, True),
            )
        else:
            recheck_owner_review_retained_sources(
                cast(Any, NoAccess()),
                principal=cast(Any, NoAccess()),
                document=document,
                now=cast(Any, True),
                dependencies=(),
            )


@pytest.mark.parametrize("change", ["version", "native_flag", "time"])
def test_copied_graph_cannot_bypass_mandatory_validation(change: str) -> None:
    document = owner_compose(owner_ready())
    if change == "version":
        document = document.model_copy(update={"version": True})
    elif change == "time":
        document = document.model_copy(update={"generated_at": 0})
    else:
        assert document.google_budget_input_catalogs is not None
        catalog = document.google_budget_input_catalogs[0]
        native = catalog.catalog.native_observation.model_copy(
            update={"advertising_writes_enabled": 0}
        )
        catalog = catalog.model_copy(
            update={"catalog": catalog.catalog.model_copy(update={"native_observation": native})}
        )
        document = document.model_copy(update={"google_budget_input_catalogs": (catalog,)})
    with pytest.raises(ValueError):
        _Context(
            cast(Any, NoAccess()),
            cast(Any, NoAccess()),
            document,
            datetime.now(UTC),
            required_pair=PAIR,
        )


class Root:
    is_active = True


class CleanSession:
    """No SQL fixture for inspecting only constructor-local canonical ownership."""

    new = dirty = deleted = ()
    closed = False

    def __init__(self) -> None:
        self.root = Root()

    def get_transaction(self) -> Root:
        return self.root

    def in_nested_transaction(self) -> bool:
        return False

    def connection(self) -> "CleanSession":
        return self


@pytest.mark.parametrize("version", [5, 6])
def test_context_keeps_checked_copy_and_old_default(version: int) -> None:
    document = compose(ready()) if version == 5 else owner_compose(owner_ready())
    db = CleanSession()
    context = _Context(
        cast(Any, db),
        cast(Any, NoAccess()),
        document,
        datetime.now(UTC),
        required_pair=PAIR if version == 6 else None,
    )
    assert context.document is not document
    assert context.document.model_dump_json() == document.model_dump_json()
    assert context.root is cast(Any, db.root) and context.connection is cast(Any, db)


def test_matching_unsupported_pair_still_requires_canonical_creative_descriptor() -> None:
    from app.planning_documents.documents import PlanVersion

    from tests.test_planning_document_contracts import packet

    # Legacy-shaped schema permits this test-only identity; context does not.
    document = PlanVersion.model_validate(packet())
    pair = (document.policy_version, document.generator_version)
    assert pair == ("test-v1", "test-v1")
    with pytest.raises(ValueError):
        _Context(
            cast(Any, NoAccess()),
            cast(Any, NoAccess()),
            document,
            datetime.now(UTC),
            required_pair=pair,
        )
