"""Closed current API authentication/configuration deltas; no execution exemptions."""

import re
import time
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from app.customers.access import CSRF_COOKIE, SESSION_COOKIE, TTL_SECONDS, digest
from app.customers.models import CustomerUser
from app.publication.contracts import fingerprint
from app.publication.execution_authorization import owner_authorizer
from app.publication.social_catalog import MetaConfigurationProfile
from app.publication.social_review_contracts import (
    LegacySocialConfigurationDocumentV1,
    MetaNoDSAAnswer,
    SocialConfigurationDocument,
    SocialRequirements,
    TikTokCoverAnswer,
)
from app.publication.social_review_service import selection
from app.shopify.security import utc
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.social_producer_retained_fixture import (
    SocialProducerSource,
    graph,
    load_source,
    retained_social_producer,
)
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import FakeProvider, login
from tests.test_customer_identity import replicas as identity_replicas

Rows = dict[str, list[dict[str, Any]]]


def expected_api_document(db: Session, source: SocialProducerSource) -> SocialConfigurationDocument:
    _, account, catalog, producer, actor, store, cover, _ = load_source(db, source)
    profile = next(iter(producer.profiles.values()))
    if isinstance(profile, MetaConfigurationProfile):
        profile = profile.model_copy(update={"dsa_required": False})
    option = catalog.options[0].model_copy(update={"profile_digest": profile.digest()})
    catalog = catalog.model_copy(update={"options": [option]})
    return selection(
        db, account.workspace_id, actor, account, catalog, option.identifier(catalog.request),
        profile, SocialRequirements(
            profile_digest=profile.digest(), requirements_digest="a" * 64,
            wording_version="contract-test-v1", verified=True, dsa_required=False,
            wording="Offline Test: Review This No-DSA Profile And Its Exact Media.",
        ), MetaNoDSAAnswer(special_category_answer="none_applicable")
        if source.ids.provider == "meta_ads" else TikTokCoverAnswer(reviewed_pair=True),
        cover, "contract_test", store, lambda: NOW, owner_authorizer,
    )


@dataclass
class SocialApiLoginEvidence:
    document: SocialConfigurationDocument
    actor: str
    bound: Rows | None = None
    original: Rows | None = None
    alice_session: str | None = None
    issued_after: int = 0

    def login(self, source: SocialProducerSource, alice: TestClient, bob: TestClient) -> None:
        assert self.bound is None
        before = graph(source.engine)
        assert before["customer_sessions"] == before["customer_token_exchanges"] == []
        original = next(row for row in before["customer_users"] if row["id"] == self.actor)
        assert original["subject"] == self.actor and original["issuer"] == "mock"
        started = int(time.time())
        assert login(alice, self.actor + ":1") == self.actor
        foreign = login(bob, "other:1")
        ended = int(time.time())
        assert foreign != self.actor and re.fullmatch(r"[a-f0-9]{32}", foreign)
        actual = graph(source.engine)
        expected = deepcopy(before)
        expected["customer_users"].append(dict(
            id=foreign, issuer=original["issuer"], subject="other", email=original["email"],
            status="active",
        ))
        expected["customer_users"].sort(key=lambda row: row["id"])
        sessions = []
        for client, actor in ((alice, self.actor), (bob, foreign)):
            identifier = digest(client.cookies[SESSION_COOKIE])
            row = next(row for row in actual["customer_sessions"] if row["digest"] == identifier)
            assert started <= row["created_at"] <= ended
            assert started <= row["authenticated_at"] <= ended
            assert row == dict(
                digest=identifier, user_id=actor, csrf_digest=digest(client.cookies[CSRF_COOKIE]),
                created_at=row["created_at"], authenticated_at=row["authenticated_at"],
                expires_at=row["created_at"] + TTL_SECONDS, revoked_at=None,
            )
            sessions.append(row)
        expected["customer_sessions"] = sorted(sessions, key=lambda row: row["digest"])
        receipts = actual["customer_token_exchanges"]
        assert len(receipts) == 2
        assert {row["digest"] for row in receipts} == {digest(self.actor + ":1"), digest("other:1")}
        for row in receipts:
            assert started + 3600 <= row["expires_at"] <= ended + 3600
            assert set(row) == {"digest", "expires_at"}
        expected["customer_token_exchanges"] = receipts
        assert actual == expected
        self.original = deepcopy(before)
        self.bound = deepcopy(actual)
        self.alice_session = digest(alice.cookies[SESSION_COOKIE])
        self.issued_after = started

    def assert_delta(self, before: Rows, actual: Rows) -> None:
        if self.bound is None:
            assert actual == before
            return
        expected = deepcopy(self.bound)
        # Revalidate the source snapshot, not a generic acceptance of bound rows.
        for name in before:
            if name not in {"customer_users", "customer_sessions", "customer_token_exchanges"}:
                assert expected[name] == before[name]
        sessions = expected["customer_sessions"]
        revoked = next(row for row in actual["customer_sessions"]
                       if row["digest"] == self.alice_session)["revoked_at"]
        assert type(revoked) is int and self.issued_after <= revoked <= int(time.time())
        next(row for row in sessions if row["digest"] == self.alice_session)["revoked_at"] = revoked
        reviews = "customer_social_configuration_reviews"
        approvals = "customer_social_configuration_approvals"
        assert before[reviews] == before[approvals] == []
        document = self.document
        legacy = LegacySocialConfigurationDocumentV1.model_validate({
            **{k: v for k, v in document.model_dump(mode="json").items()
               if k not in {"configuration", "configuration_digest"}},
            "schema_version": "inlet.social-configuration-review.v1",
            "requirements": {k: v for k, v in document.requirements.model_dump(mode="json").items()
                             if k != "wording"},
        })
        by_digest: dict[str, SocialConfigurationDocument | LegacySocialConfigurationDocumentV1] = {
            document.digest(): document, legacy.digest(): legacy,
        }
        assert len(actual[reviews]) == len(actual[approvals]) == 2
        assert {row["digest"] for row in actual[reviews]} == set(by_digest)
        for row in actual[reviews]:
            value = by_digest[row["digest"]]
            assert re.fullmatch(r"[a-f0-9]{32}", row["id"])
            assert utc(row["created_at"]) == NOW
            assert row == dict(
                id=row["id"], workspace_id=value.request.account.workspace_id,
                account_id=value.request.account.account.account_id,
                integration_id=value.request.account.account.connection_id,
                draft_id=value.request.draft_id, source_revision=value.request.draft_revision,
                digest=value.digest(), document=value.model_dump(mode="json"),
                created_by=self.actor, created_at=row["created_at"],
            )
            approval = next(a for a in actual[approvals] if a["review_id"] == row["id"])
            assert utc(approval["confirmed_at"]) == NOW
            stamp = dict(
                review_id=row["id"], workspace_id=row["workspace_id"],
                review_digest=row["digest"], actor=self.actor, confirmed_at=NOW.isoformat(),
            )
            assert approval == {
                **stamp, "confirmed_at": approval["confirmed_at"],
                "digest": fingerprint("inlet.social-configuration-approval.v1", stamp),
            }
        expected[reviews], expected[approvals] = actual[reviews], actual[approvals]
        assert actual == expected


@pytest.fixture
def social_api_source(
    customer_engine: Engine, tmp_path: Path, request: pytest.FixtureRequest,
) -> Iterator[SocialProducerSource]:
    assert request.node.originalname == "test_owned_exact_no_dsa_api"
    platform = request.node.callspec.params["platform"]
    video = request.getfixturevalue("encoded")() if platform == "tiktok_ads" else None
    with retained_social_producer(
        customer_engine, tmp_path / "api-original", platform, video, None, consumer="api",
    ) as source:
        yield source


@pytest.fixture
def social_api_replicas(
    social_api_source: SocialProducerSource, monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, TestClient, FakeProvider]:
    clients = cast(tuple[TestClient, TestClient, FakeProvider],
                   cast(Any, identity_replicas).__wrapped__(social_api_source.engine, monkeypatch))
    with Session(social_api_source.engine) as db:
        user = db.get(CustomerUser, social_api_source.ids.actor_id)
        assert user and user.issuer == "mock" and user.subject == user.id
        clients[2].issuer, clients[2].email = user.issuer, user.email
    return clients


def assert_closed_api_delta(source: SocialProducerSource) -> None:
    """Adversarial copies of genuine rows; never mutate the actual DB/authority."""
    evidence = source.api_evidence
    assert evidence and evidence.original is not None
    actual = graph(source.engine)
    evidence.assert_delta(evidence.original, actual)
    with pytest.raises(AssertionError):
        SocialApiLoginEvidence(evidence.document, evidence.actor).assert_delta(
            evidence.original, actual
        )
    for table in (
        "customer_sessions", "customer_social_configuration_approvals",
        "customer_social_configuration_reviews",
    ):
        changed = deepcopy(actual)
        changed[table].append(deepcopy(changed[table][0]))
        with pytest.raises(AssertionError):
            evidence.assert_delta(evidence.original, changed)
    changed = deepcopy(actual)
    original_user = next(row for row in changed["customer_users"] if row["id"] == evidence.actor)
    original_user["issuer"] = "changed"
    with pytest.raises(AssertionError):
        evidence.assert_delta(evidence.original, changed)
    changed = deepcopy(actual)
    changed["workspaces"][0]["name"] = "changed"
    with pytest.raises(AssertionError):
        evidence.assert_delta(evidence.original, changed)
