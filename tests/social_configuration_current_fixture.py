"""Exact current configuration evidence over a closed original source."""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Never

import pytest
from app.publication.contracts import fingerprint
from app.publication.coordinator_contracts import CreationRuntime
from app.publication.execution_authorization import owner_authorizer
from app.publication.social_catalog import MetaConfigurationProfile
from app.publication.social_review_contracts import (
    MetaNoDSAAnswer,
    SocialConfigurationDocument,
    SocialRequirements,
    TikTokCoverAnswer,
)
from app.publication.social_review_service import selection
from app.shopify.security import utc
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.social_producer_retained_fixture import (
    SocialProducerIds,
    SocialProducerSource,
    load_source,
    retained_social_producer,
)
from tests.test_commerce_measurement import NOW


def forbidden(*args: Any, **kwargs: Any) -> Never:
    raise AssertionError("configuration metadata must not invoke execution ports")


class ForbiddenTransport:
    validate_only = staticmethod(forbidden)
    apply_once = staticmethod(forbidden)
    read_back = staticmethod(forbidden)
    reconcile = staticmethod(forbidden)


def metadata_runtime() -> CreationRuntime:
    return CreationRuntime(
        environment="contract_test",
        qualification_reader=forbidden,
        exposure_reader=forbidden,
        google=ForbiddenTransport(),
        meta=ForbiddenTransport(),
        tiktok=ForbiddenTransport(),
        google_context=forbidden,
        social_context=forbidden,
    )


def expected_document(db: Session, source: SocialProducerSource) -> SocialConfigurationDocument:
    _, account, catalog, producer, actor, store, cover, _ = load_source(db, source)
    profile = next(iter(producer.profiles.values()))
    if isinstance(profile, MetaConfigurationProfile):
        profile = profile.model_copy(update={"dsa_required": False})
    option = catalog.options[0].model_copy(update={"profile_digest": profile.digest()})
    catalog = catalog.model_copy(update={"options": [option]})
    return selection(
        db, account.workspace_id, actor, account, catalog, option.identifier(catalog.request),
        profile,
        SocialRequirements(
            profile_digest=profile.digest(), requirements_digest="a" * 64,
            wording_version="explicit-test-rule-v1", verified=True, dsa_required=False,
            wording="Offline Test: Review This No-DSA Profile And Its Exact Media.",
        ),
        MetaNoDSAAnswer(special_category_answer="none_applicable")
        if source.ids.provider == "meta_ads" else TikTokCoverAnswer(reviewed_pair=True),
        cover, "contract_test", store, lambda: NOW, owner_authorizer,
    )


def configuration_delta(
    expected: dict[str, list[dict[str, Any]]],
    actual: dict[str, list[dict[str, Any]]],
    ids: SocialProducerIds,
    document: SocialConfigurationDocument,
) -> None:
    reviews = "customer_social_configuration_reviews"
    approvals = "customer_social_configuration_approvals"
    assert expected[reviews] == expected[approvals] == []
    documents = [document]
    if ids.provider == "meta_ads":
        documents.append(document.model_copy(update={
            "answer": MetaNoDSAAnswer(special_category_answer="unsure"),
        }))
    assert len(actual[reviews]) == len(documents)
    by_digest = {d.digest(): d for d in documents}
    assert {row["digest"] for row in actual[reviews]} == set(by_digest)
    for row in actual[reviews]:
        value = by_digest[row["digest"]]
        assert re.fullmatch(r"[a-f0-9]{32}", row["id"])
        assert utc(row["created_at"]) == NOW
        assert row == dict(
            id=row["id"], workspace_id=ids.workspace_id, account_id=ids.account_id,
            integration_id=value.request.account.account.connection_id,
            draft_id=value.request.draft_id, source_revision=value.request.draft_revision,
            digest=value.digest(), document=value.model_dump(mode="json"),
            created_by=ids.actor_id, created_at=row["created_at"],
        )
    assert len(actual[approvals]) == 1
    approval = actual[approvals][0]
    review = next(row for row in actual[reviews] if row["digest"] == document.digest())
    assert utc(approval["confirmed_at"]) == NOW
    digest = fingerprint("inlet.social-configuration-approval.v1", dict(
        review_id=review["id"], workspace_id=ids.workspace_id, review_digest=document.digest(),
        actor=ids.actor_id, confirmed_at=NOW.isoformat(),
    ))
    assert approval == dict(
        review_id=review["id"], workspace_id=ids.workspace_id, review_digest=document.digest(),
        digest=digest, actor=ids.actor_id, confirmed_at=approval["confirmed_at"],
    )
    members = [row for row in expected["customer_memberships"]
               if row["user_id"] == ids.actor_id and row["workspace_id"] == ids.workspace_id]
    assert len(members) == 1 and members[0]["status"] == "active"
    members[0]["status"] = "suspended"
    expected[reviews] = actual[reviews]
    expected[approvals] = actual[approvals]


@pytest.fixture
def social_configuration_source(
    customer_engine: Engine, tmp_path: Path, request: pytest.FixtureRequest,
) -> Iterator[SocialProducerSource]:
    assert request.node.originalname == "test_exact_configuration_confirmation"
    provider = request.node.callspec.params["provider"]
    video = request.getfixturevalue("encoded")() if provider == "tiktok_ads" else None
    with retained_social_producer(
        customer_engine, tmp_path / "configuration-original", provider, video, None,
        consumer="configuration",
    ) as source:
        yield source
