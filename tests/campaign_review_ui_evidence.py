"""Exact current campaign browser graph, supplied bytes and ordinary login evidence."""

import hashlib
import re
import time
from copy import deepcopy
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any

import pytest
from app.campaign_review import service
from app.campaign_review.contracts import RevisionInput
from app.campaign_review.models import CampaignDraft
from app.customers.access import CSRF_COOKIE, SESSION_COOKIE, TTL_SECONDS, digest
from app.mandates import service as mandates
from app.mandates.models import Mandate
from app.mandates.schemas import MandateDefinition
from app.shopify.security import utc
from sqlalchemy.orm import Session

from tests.social_producer_retained_fixture import graph
from tests.test_campaign_review import definition, png
from tests.test_commerce_measurement import NOW

if TYPE_CHECKING:
    from tests.campaign_review_ui_retained_fixture import CampaignReviewUiIds, CampaignUiSource

Rows = dict[str, list[dict[str, Any]]]
MEDIA = "customer_media_objects"
DRAFTS = "customer_campaign_drafts"
REVISIONS = "customer_campaign_revisions"


@dataclass
class CampaignUiEvidence:
    ids: "CampaignReviewUiIds"
    original: Rows
    prepared: Rows | None = None
    authenticated: Rows | None = None
    definitions: dict[str, RevisionInput] = field(default_factory=dict)
    google_id: str = ""
    image_id: str = ""
    video: bytes = b""
    policy: MandateDefinition | None = None

    def media_row(self, source: "CampaignUiSource", row: dict[str, Any], data: bytes) -> None:
        mime, width, height = service.inspect_media(data)
        assert re.fullmatch(r"[a-f0-9]{32}", row["id"])
        assert utc(row["created_at"]) == NOW
        assert row == dict(id=row["id"], workspace_id=self.ids.workspace_id,
                           sha256=hashlib.sha256(data).hexdigest(), size=len(data), mime=mime,
                           width=width, height=height, created_by=self.ids.actor_id,
                           created_at=row["created_at"])
        assert source.store.read_exact(self.ids.workspace_id, row["sha256"], len(data)) == data

    def revision(self, source: "CampaignUiSource", row: dict[str, Any],
                 body: RevisionInput, revision: int, approved: bool = False) -> None:
        assert re.fullmatch(r"[a-f0-9]{32}", row["draft_id"])
        with Session(source.engine) as db:
            doc = service.artifact(db, CampaignDraft(id=row["draft_id"],
                                   workspace_id=self.ids.workspace_id, revision=revision),
                                   body, source.store, NOW)
        assert utc(row["created_at"]) == NOW
        assert (row["approved_at"] is not None) == approved
        if approved:
            assert utc(row["approved_at"]) == NOW
        assert row == dict(draft_id=row["draft_id"], revision=revision,
                           workspace_id=self.ids.workspace_id, artifact=doc.model_dump(mode="json"),
                           digest=doc.fingerprint(), created_by=self.ids.actor_id,
                           created_at=row["created_at"],
                           approved_by=self.ids.actor_id if approved else None,
                           approved_at=row["approved_at"] if approved else None)

    def bind_setup(self, source: "CampaignUiSource", google_id: str,
                   image_draft_id: str, image_id: str, video: bytes) -> None:
        assert self.prepared is None and self.authenticated is None
        assert self.original[MEDIA] == self.original[DRAFTS] == self.original[REVISIONS] == []
        actual = graph(source.engine)
        assert len(actual[MEDIA]) == 1 and actual[MEDIA][0]["id"] == image_id
        self.media_row(source, actual[MEDIA][0], png())
        with Session(source.engine) as db:
            mandate = db.get(Mandate, self.ids.mandate_id)
            assert mandate
            policy = mandates.policy(db, mandate)
            self.policy = MandateDefinition.model_validate(policy.model_dump(mode="json"))
            google = definition(db, mandate, policy.accounts[0])
            image = google.model_dump(mode="json")
            image["account"] = policy.accounts[1].model_dump(mode="json")
            image["content"] = dict(
                kind="meta_website_sales_image_v1", objective="website_sales",
                name="Supplied Image",
                landing_page="https://example.invalid/shop",
                audience={"countries": ["US"], "languages": ["en"]},
                headline="Supplied Headline", text="Image Copy", call_to_action="SHOP_NOW",
                media={"media_id": image_id, "sha256": hashlib.sha256(png()).hexdigest()},
            )
        self.definitions = {google_id: google, image_draft_id: RevisionInput.model_validate(image)}
        assert len(actual[DRAFTS]) == len(actual[REVISIONS]) == 2
        for row in actual[DRAFTS]:
            assert row["id"] in self.definitions
            assert row == dict(id=row["id"], workspace_id=self.ids.workspace_id, revision=1)
        for row in actual[REVISIONS]:
            self.revision(source, row, self.definitions[row["draft_id"]], 1)
        expected = deepcopy(self.original)
        for name in (MEDIA, DRAFTS, REVISIONS):
            expected[name] = actual[name]
        assert actual == expected
        self.google_id, self.image_id, self.video = google_id, image_id, video
        self.prepared = deepcopy(actual)

    def bind_login(self, source: "CampaignUiSource", headers: list[tuple[bytes, bytes]],
                   started: int, ended: int) -> None:
        assert self.prepared is not None and self.authenticated is None
        assert started <= ended <= int(time.time())
        expected = deepcopy(self.prepared)
        assert expected["customer_sessions"] == expected["customer_token_exchanges"] == []
        cookies: dict[str, str] = {}
        for key, value in headers:
            if key.lower() == b"set-cookie":
                parsed = SimpleCookie()
                parsed.load(value.decode("latin1"))
                for name, morsel in parsed.items():
                    assert name in {SESSION_COOKIE, CSRF_COOKIE} and name not in cookies
                    assert morsel["secure"] and morsel["samesite"].lower() == "strict"
                    cookies[name] = digest(morsel.value)
        assert set(cookies) == {SESSION_COOKIE, CSRF_COOKIE}
        actual = graph(source.engine)
        assert len(actual["customer_sessions"]) == len(actual["customer_token_exchanges"]) == 1
        row = actual["customer_sessions"][0]
        assert started <= row["created_at"] <= ended
        assert started <= row["authenticated_at"] <= ended
        assert row == dict(digest=cookies[SESSION_COOKIE], csrf_digest=cookies[CSRF_COOKIE],
                           user_id=self.ids.actor_id, created_at=row["created_at"],
                           authenticated_at=row["authenticated_at"],
                           expires_at=row["created_at"] + TTL_SECONDS, revoked_at=None)
        receipt = actual["customer_token_exchanges"][0]
        assert set(receipt) == {"digest", "expires_at"}
        assert receipt["digest"] == digest("review-owner:browser")
        assert started + 3600 <= receipt["expires_at"] <= ended + 3600
        expected["customer_sessions"] = [row]
        expected["customer_token_exchanges"] = [receipt]
        assert actual == expected
        self.authenticated = deepcopy(actual)

    def browser_bodies(self, video_id: str) -> dict[str, RevisionInput]:
        # Policy/date/account inputs were copied before any browser request.
        assert self.policy is not None
        policy = MandateDefinition.model_validate(self.policy.model_dump(mode="json"))
        bodies = {}
        for account, name, kind in zip(policy.accounts,
                ("New Google Draft", "New Meta Draft", "Supplied Video Draft"),
                ("google_search_v1", "meta_website_sales_image_v1",
                 "tiktok_website_conversion_video_v1"), strict=True):
            content: dict[str, Any] = dict(kind=kind, objective="website_conversion"
                if kind.startswith("tiktok") else "website_sales", name=name,
                landing_page="https://example.invalid/shop",
                audience={"countries": ["US"], "languages": ["en"]})
            if kind == "google_search_v1":
                content.update(headlines=["First Headline", "Second Headline", "Third Headline"],
                               descriptions=["First Description", "Second Description"],
                               exact_keywords=["supplied product"])
            else:
                video = kind.startswith("tiktok")
                content.update(text="Supplied Video Copy", call_to_action="SHOP_NOW", media={
                    "media_id": video_id if video else self.image_id,
                    "sha256": hashlib.sha256(self.video if video else png()).hexdigest()})
                if not video:
                    content["headline"] = "Supplied Headline"
            bodies[name] = RevisionInput.model_validate(dict(
                account=account, mandate_id=self.ids.mandate_id,
                mandate_revision=self.ids.mandate_revision, currency=policy.currency,
                budget_micros=60,
                starts_at=policy.starts_at.replace(second=0, microsecond=0),
                ends_at=policy.ends_at.replace(second=0, microsecond=0), content=content))
        return bodies

    def assert_final(self, source: "CampaignUiSource", before: Rows, actual: Rows) -> None:
        assert before == self.original
        assert self.authenticated is not None and self.prepared is not None
        expected = deepcopy(self.authenticated)
        assert len(actual[MEDIA]) == 2
        image = next(row for row in actual[MEDIA] if row["id"] == self.image_id)
        video = next(row for row in actual[MEDIA] if row["id"] != self.image_id)
        assert image == self.prepared[MEDIA][0]
        self.media_row(source, image, png())
        self.media_row(source, video, self.video)
        assert len(actual[DRAFTS]) == 5 and len(actual[REVISIONS]) == 7
        bodies = self.browser_bodies(video["id"])
        new_rows = [row for row in actual[REVISIONS] if row["draft_id"] not in self.definitions]
        assert len(new_rows) == 3
        names: set[str] = set()
        definitions = dict(self.definitions)
        for row in new_rows:
            name = row["artifact"]["definition"]["content"]["name"]
            assert name in bodies and name not in names
            names.add(name)
            definitions[row["draft_id"]] = bodies[name]
        assert names == set(bodies) and len(definitions) == 5
        for row in actual[DRAFTS]:
            assert row["id"] in definitions
            assert row == dict(id=row["id"], workspace_id=self.ids.workspace_id,
                               revision=3 if row["id"] == self.google_id else 1)
        edited = self.definitions[self.google_id].model_dump(mode="json")
        edited["content"]["name"] = "<img src=x onerror=alert(1)> New Name"
        for row in actual[REVISIONS]:
            is_google = row["draft_id"] == self.google_id
            revision = row["revision"]
            assert revision in ({1, 2, 3} if is_google else {1})
            body = RevisionInput.model_validate(edited) if is_google and revision > 1 else (
                definitions[row["draft_id"]])
            self.revision(source, row, body, revision, is_google and revision == 1)
            if row["draft_id"] in self.definitions and revision == 1:
                old = next(r for r in self.prepared[REVISIONS]
                           if r["draft_id"] == row["draft_id"])
                excluded = {"approved_by", "approved_at"}
                assert {k: v for k, v in row.items() if k not in excluded} == {
                    k: v for k, v in old.items() if k not in excluded}
        for name in (MEDIA, DRAFTS, REVISIONS):
            expected[name] = actual[name]
        member = next(row for row in expected["customer_memberships"]
                      if (row["user_id"], row["workspace_id"]) == (
                          self.ids.actor_id, self.ids.workspace_id))
        assert member["role"] == "owner"
        member["role"] = "viewer"
        assert actual == expected

    def negatives(self, source: "CampaignUiSource") -> None:
        actual = graph(source.engine)
        altered_evidence = deepcopy(self)
        altered_evidence.original["customer_users"][0]["subject"] = "changed"
        with pytest.raises(AssertionError):
            altered_evidence.assert_final(source, self.original, actual)
        before = deepcopy(self.original)
        before["customer_users"][0]["subject"] = "changed"
        with pytest.raises(AssertionError):
            self.assert_final(source, before, actual)
        for table in (MEDIA, DRAFTS, REVISIONS, "customer_sessions"):
            changed = deepcopy(actual)
            changed[table].append(deepcopy(changed[table][0]))
            with pytest.raises(AssertionError):
                self.assert_final(source, self.original, changed)
        for table, key, value in ((MEDIA, "sha256", "a" * 64),
                                  (DRAFTS, "workspace_id", self.ids.workspace_id + 1),
                                  (REVISIONS, "approved_by", "foreign"),
                                  ("customer_memberships", "role", "owner")):
            changed = deepcopy(actual)
            changed[table][0][key] = value
            with pytest.raises(AssertionError):
                self.assert_final(source, self.original, changed)
        with pytest.raises(AssertionError):
            self.bind_login(source, [], int(time.time()), int(time.time()))
