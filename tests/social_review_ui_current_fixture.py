"""Closed real-browser social configuration and authentication evidence."""

import re
import time
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

import pytest
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
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.social_producer_retained_fixture import (
    SocialProducerSource,
    graph,
    load_source,
    retained_social_producer,
)
from tests.test_commerce_measurement import NOW

Rows = dict[str, list[dict[str, Any]]]


def expected_ui_document(db: Session, source: SocialProducerSource) -> SocialConfigurationDocument:
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
            wording_version="browser-test-v1", verified=True, dsa_required=False,
            wording="Offline Test: Review This No-DSA Profile And Its Exact Media.",
        ), MetaNoDSAAnswer(special_category_answer="none_applicable")
        if source.ids.provider == "meta_ads" else TikTokCoverAnswer(reviewed_pair=True),
        cover, "contract_test", store, lambda: NOW, owner_authorizer,
    )


@dataclass
class SocialUiEvidence:
    document: SocialConfigurationDocument
    actor: str
    original: Rows
    named: Rows | None = None
    bound: Rows | None = None
    logout_interval: tuple[int, int] | None = None

    def record_workspace_name_change(
        self, source: SocialProducerSource, started: datetime, ended: datetime,
    ) -> None:
        assert self.named is None and self.bound is None
        assert started <= ended <= datetime.now(UTC)
        actual = graph(source.engine)
        self.validate_name_change(actual, started, ended)
        self.named = deepcopy(actual)

    def validate_name_change(self, actual: Rows, started: datetime, ended: datetime) -> None:
        expected = deepcopy(self.original)
        wid = self.document.request.account.workspace_id
        workspace = next(row for row in expected["workspaces"] if row["id"] == wid)
        row = next(row for row in actual["workspaces"] if row["id"] == wid)
        assert started <= utc(row["updated_at"]) <= ended
        workspace["name"] = "<img src=x>"
        workspace["updated_at"] = row["updated_at"]
        assert actual == expected

    def named_graph(self) -> Rows:
        assert self.named is not None
        return deepcopy(self.named)

    def record_login(
        self, source: SocialProducerSource, headers: list[tuple[bytes, bytes]],
        started: int, ended: int,
    ) -> None:
        assert self.bound is None and started <= ended <= int(time.time())
        expected = self.named_graph()
        assert expected["customer_sessions"] == expected["customer_token_exchanges"] == []
        actor = next(row for row in expected["customer_users"] if row["id"] == self.actor)
        assert actor["issuer"] == "mock" and actor["subject"] == self.actor
        cookies: dict[str, str] = {}
        for name, value in headers:
            if name.lower() != b"set-cookie":
                continue
            parsed = SimpleCookie()
            parsed.load(value.decode("latin1"))
            for key, morsel in parsed.items():
                assert key in {SESSION_COOKIE, CSRF_COOKIE} and key not in cookies
                assert morsel["secure"] and morsel["samesite"].lower() == "strict"
                cookies[key] = digest(morsel.value)
        assert set(cookies) == {SESSION_COOKIE, CSRF_COOKIE}
        actual = graph(source.engine)
        assert len(actual["customer_sessions"]) == len(actual["customer_token_exchanges"]) == 1
        row = actual["customer_sessions"][0]
        assert started <= row["created_at"] <= ended
        assert started <= row["authenticated_at"] <= ended
        assert row == dict(
            digest=cookies[SESSION_COOKIE], csrf_digest=cookies[CSRF_COOKIE], user_id=self.actor,
            created_at=row["created_at"], authenticated_at=row["authenticated_at"],
            expires_at=row["created_at"] + TTL_SECONDS, revoked_at=None,
        )
        receipt = actual["customer_token_exchanges"][0]
        assert set(receipt) == {"digest", "expires_at"}
        assert receipt["digest"] == digest(self.actor + ":browser")
        assert started + 3600 <= receipt["expires_at"] <= ended + 3600
        expected["customer_sessions"] = [row]
        expected["customer_token_exchanges"] = [receipt]
        assert actual == expected
        self.bound = deepcopy(actual)

    def record_logout(self, started: int, ended: int) -> None:
        assert self.bound is not None and self.logout_interval is None
        assert started <= ended <= int(time.time())
        self.logout_interval = (started, ended)

    def assert_delta(self, before: Rows, actual: Rows) -> None:
        assert self.original == before
        if self.bound is None:
            assert actual == before
            return
        assert self.logout_interval is not None
        expected = deepcopy(self.bound)
        assert len(actual["customer_sessions"]) == 1
        revoked = actual["customer_sessions"][0]["revoked_at"]
        assert type(revoked) is int
        assert self.logout_interval[0] <= revoked <= self.logout_interval[1]
        expected["customer_sessions"][0]["revoked_at"] = revoked
        reviews = "customer_social_configuration_reviews"
        approvals = "customer_social_configuration_approvals"
        assert before[reviews] == before[approvals] == []
        assert len(actual[reviews]) == len(actual[approvals]) == 1
        row, approval = actual[reviews][0], actual[approvals][0]
        value = self.document
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
        assert utc(approval["confirmed_at"]) == NOW
        stamp = dict(review_id=row["id"], workspace_id=row["workspace_id"],
                     review_digest=row["digest"], actor=self.actor, confirmed_at=NOW.isoformat())
        assert approval == {
            **stamp, "confirmed_at": approval["confirmed_at"],
            "digest": fingerprint("inlet.social-configuration-approval.v1", stamp),
        }
        expected[reviews], expected[approvals] = actual[reviews], actual[approvals]
        assert actual == expected


def assert_ui_copy_denials(source: SocialProducerSource) -> None:
    evidence = source.ui_evidence
    assert evidence is not None
    actual = graph(source.engine)
    assert evidence.named is not None
    with pytest.raises(AssertionError):
        evidence.record_workspace_name_change(source, datetime.now(UTC), datetime.now(UTC))
    row = next(row for row in evidence.named["workspaces"]
               if row["id"] == source.ids.workspace_id)
    at = utc(row["updated_at"])
    evidence.validate_name_change(evidence.named, at, at)
    with pytest.raises(AssertionError):
        evidence.validate_name_change(evidence.named, at + timedelta(seconds=1),
                                      at + timedelta(seconds=2))
    for field, value in (("name", "changed"), ("client_name", "changed"),
                         ("updated_at", at + timedelta(seconds=1))):
        changed = deepcopy(evidence.named)
        changed["workspaces"][0][field] = value
        with pytest.raises(AssertionError):
            evidence.validate_name_change(changed, at, at)
    evidence.assert_delta(evidence.original, actual)
    changed_before = deepcopy(evidence.original)
    changed_before["customer_users"][0]["issuer"] = "changed"
    with pytest.raises(AssertionError):
        evidence.assert_delta(changed_before, actual)
    with pytest.raises(AssertionError):
        SocialUiEvidence(evidence.document, evidence.actor, evidence.original).assert_delta(
            evidence.original, actual,
        )
    for table in ("customer_sessions", "customer_social_configuration_reviews",
                  "customer_social_configuration_approvals"):
        changed = deepcopy(actual)
        changed[table].append(deepcopy(changed[table][0]))
        with pytest.raises(AssertionError):
            evidence.assert_delta(evidence.original, changed)
    for table, field in (("workspaces", "name"), ("customer_sessions", "user_id"),
                         ("customer_sessions", "csrf_digest")):
        changed = deepcopy(actual)
        changed[table][0][field] = "changed"
        with pytest.raises(AssertionError):
            evidence.assert_delta(evidence.original, changed)


@pytest.fixture
def social_ui_source(
    customer_engine: Engine, tmp_path: Path, request: pytest.FixtureRequest,
) -> Iterator[SocialProducerSource]:
    assert request.node.originalname == "test_social_review_real_browser"
    platform = request.node.callspec.params["platform"]
    video = request.getfixturevalue("encoded")() if platform == "tiktok_ads" else None
    with retained_social_producer(
        customer_engine, tmp_path / "ui-original", platform, video, None, consumer="ui",
    ) as source:
        yield source
