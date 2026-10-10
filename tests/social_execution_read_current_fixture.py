"""Closed current API authentication/configuration deltas; no execution exemptions."""

import re
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.customers.access import CSRF_COOKIE, SESSION_COOKIE, TTL_SECONDS, digest
from app.publication.contracts import fingerprint
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
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.social_producer_retained_fixture import (
    SocialProducerSource,
    graph,
    load_source,
)
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import login

Rows = dict[str, list[dict[str, Any]]]


def expected_execution_document(
    db: Session, source: SocialProducerSource
) -> SocialConfigurationDocument:
    _, account, catalog, producer, actor, store, cover, _ = load_source(db, source)
    profile = next(iter(producer.profiles.values()))
    if isinstance(profile, MetaConfigurationProfile):
        profile = profile.model_copy(update={"dsa_required": False})
    option = catalog.options[0].model_copy(update={"profile_digest": profile.digest()})
    catalog = catalog.model_copy(update={"options": [option]})
    return selection(
        db,
        account.workspace_id,
        actor,
        account,
        catalog,
        option.identifier(catalog.request),
        profile,
        SocialRequirements(
            profile_digest=profile.digest(),
            requirements_digest="a" * 64,
            wording_version="offline-v1",
            verified=True,
            dsa_required=False,
            wording="Offline Profile: Explicit No Special Category And Exact Media.",
        ),
        MetaNoDSAAnswer(special_category_answer="none_applicable")
        if source.ids.provider == "meta_ads"
        else TikTokCoverAnswer(reviewed_pair=True),
        cover,
        "contract_test",
        store,
        lambda: NOW,
        owner_authorizer,
    )


@dataclass
class SocialExecutionReadEvidence:
    document: SocialConfigurationDocument
    actor: str
    bound: Rows | None = None
    original: Rows | None = None
    alice_session: str | None = None
    issued_after: int = 0
    logout_bounds: tuple[int, int] | None = None

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
        expected["customer_users"].append(
            dict(
                id=foreign,
                issuer=original["issuer"],
                subject="other",
                email=original["email"],
                status="active",
            )
        )
        expected["customer_users"].sort(key=lambda row: row["id"])
        sessions = []
        for client, actor in ((alice, self.actor), (bob, foreign)):
            identifier = digest(client.cookies[SESSION_COOKIE])
            row = next(row for row in actual["customer_sessions"] if row["digest"] == identifier)
            assert started <= row["created_at"] <= ended
            assert started <= row["authenticated_at"] <= ended
            assert row == dict(
                digest=identifier,
                user_id=actor,
                csrf_digest=digest(client.cookies[CSRF_COOKIE]),
                created_at=row["created_at"],
                authenticated_at=row["authenticated_at"],
                expires_at=row["created_at"] + TTL_SECONDS,
                revoked_at=None,
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

    def logout(self, client: TestClient, headers: dict[str, str]) -> None:
        assert self.bound is not None and self.logout_bounds is None
        started = int(time.time())
        assert client.delete("/api/customer/v1/session", headers=headers).status_code == 204
        self.logout_bounds = (started, int(time.time()))

    def assert_delta(self, before: Rows, actual: Rows) -> None:
        if self.bound is None:
            assert actual == before
            return
        assert self.original == before
        expected = deepcopy(self.bound)
        # Revalidate the source snapshot, not a generic acceptance of bound rows.
        for name in before:
            if name not in {"customer_users", "customer_sessions", "customer_token_exchanges"}:
                assert expected[name] == before[name]
        sessions = expected["customer_sessions"]
        revoked = next(
            row for row in actual["customer_sessions"] if row["digest"] == self.alice_session
        )["revoked_at"]
        assert self.logout_bounds is not None
        started, ended = self.logout_bounds
        assert self.issued_after <= started <= ended <= int(time.time())
        assert type(revoked) is int and started <= revoked <= ended
        next(row for row in sessions if row["digest"] == self.alice_session)["revoked_at"] = revoked
        reviews = "customer_social_configuration_reviews"
        approvals = "customer_social_configuration_approvals"
        assert before[reviews] == before[approvals] == []
        document = self.document
        by_digest = {document.digest(): document}
        assert len(actual[reviews]) == len(actual[approvals]) == 1
        assert {row["digest"] for row in actual[reviews]} == set(by_digest)
        for row in actual[reviews]:
            value = by_digest[row["digest"]]
            assert re.fullmatch(r"[a-f0-9]{32}", row["id"])
            assert utc(row["created_at"]) == NOW
            assert row == dict(
                id=row["id"],
                workspace_id=value.request.account.workspace_id,
                account_id=value.request.account.account.account_id,
                integration_id=value.request.account.account.connection_id,
                draft_id=value.request.draft_id,
                source_revision=value.request.draft_revision,
                digest=value.digest(),
                document=value.model_dump(mode="json"),
                created_by=self.actor,
                created_at=row["created_at"],
            )
            approval = next(a for a in actual[approvals] if a["review_id"] == row["id"])
            assert utc(approval["confirmed_at"]) == NOW
            stamp = dict(
                review_id=row["id"],
                workspace_id=row["workspace_id"],
                review_digest=row["digest"],
                actor=self.actor,
                confirmed_at=NOW.isoformat(),
            )
            assert approval == {
                **stamp,
                "confirmed_at": approval["confirmed_at"],
                "digest": fingerprint("inlet.social-configuration-approval.v1", stamp),
            }
        expected[reviews], expected[approvals] = actual[reviews], actual[approvals]
        assert actual == expected
