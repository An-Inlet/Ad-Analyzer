"""Old public V5 refusal/normalization independent of SQL state."""

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from app.planning_documents.creative_currentness import capture_creative_retained_source
from app.planning_documents.creative_history import (
    creative_local_witness,
    validate_creative_local_dependency,
)
from app.planning_documents.retained_sources import RetainedSourcesChanged

from tests.owner_review_v6_fixture import ready as owner_ready
from tests.test_creative_plan_composer import compose, ready
from tests.test_owner_review_v6_pure import compose as owner_compose


class NoSQL:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError("invalid document must fail before SQL")


def test_malformed_v5_preserves_existing_unavailable_boundary() -> None:
    document = compose(ready())
    malformed = document.model_copy(update={"version": True})
    with pytest.raises(RetainedSourcesChanged, match="proof_unavailable"):
        capture_creative_retained_source(
            cast(Any, NoSQL()),
            principal=cast(Any, NoSQL()),
            document=malformed,
            now=datetime.now(UTC),
        )


def test_old_public_creative_ports_do_not_admit_v6() -> None:
    document = owner_compose(owner_ready())
    with pytest.raises(ValueError, match="exact creative document"):
        creative_local_witness(document)
    with pytest.raises(ValueError, match="exact creative document"):
        validate_creative_local_dependency(document, ())
    with pytest.raises(RetainedSourcesChanged, match="proof_unavailable"):
        capture_creative_retained_source(
            cast(Any, NoSQL()),
            principal=cast(Any, NoSQL()),
            document=document,
            now=datetime.now(UTC),
        )
