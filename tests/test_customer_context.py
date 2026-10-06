"""Three optional contexts cannot create revenue or persist contact payloads."""

from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import pytest
from app.commerce.ledger import apply_order, identity_key
from app.commerce.models import CommerceEntry, CommerceOrder, CommerceSuppression
from app.customer_context.contracts import (
    ContextPage,
    CustomerProvider,
    FixtureIdentityMapping,
    ProfileContext,
    VerifiedCustomerMapping,
)
from app.customer_context.service import preview
from app.customer_context.wire import ProfileReader
from app.settings import Settings, settings
from app.shopify.security import Vault
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from app.workspaces.models import WorkspaceIntegration
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW, agreement, setup, source
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration
from tests.test_tiktok_sources import configured as configured


class Reader:
    mode: Literal["fixture"] = "fixture"

    def __init__(self, provider: CustomerProvider) -> None:
        self.provider = provider
        self.repeated = False

    def page(self, account_id: str, token: str, cursor: str | None, now: datetime) -> ContextPage:
        return ContextPage(
            account_id=account_id,
            profiles=[
                ProfileContext(source_id="known", email_status="subscribed", as_of=now),
                ProfileContext(source_id="unknown", as_of=now),
            ],
            next_cursor="repeat" if self.repeated else None,
        )


@pytest.mark.parametrize("provider", ["klaviyo", "hubspot", "omnisend"])
def test_canonical_context_no_duplicate_sales_and_scope(
    customer_engine: Engine,
    configuration: Settings,
    configured: None,
    monkeypatch: pytest.MonkeyPatch,
    provider: CustomerProvider,
) -> None:
    for name in ("shopify_identifier_hash_key", "shopify_token_encryption_key"):
        monkeypatch.setattr(settings, name, getattr(configuration, name))
    with Session(customer_engine) as db:
        native, store = setup(db, configuration)
        apply_order(db, store, native, source(), [agreement()], configuration, NOW)
        integration = WorkspaceIntegration(
            workspace_id=store.workspace_id,
            provider=provider,
            status="active",
            integration_key=provider,
            display_name="Fixture",
        )
        db.add(integration)
        db.flush()
        cid = uuid4().hex
        row = SourceConnection(
            id=cid,
            workspace_id=store.workspace_id,
            integration_id=integration.id,
            provider=provider,
            external_id="fixture",
            encrypted_grant=SourceVault().seal(
                store.workspace_id,
                provider,
                cid,
                {"access_token": "synthetic", "expires_at": (NOW + timedelta(days=1)).isoformat()},
            ),
            status="connected",
            generation=1,
            window_start=NOW.date(),
            window_end=NOW.date(),
            staged={},
        )
        db.add(row)
        db.commit()
        mapping = FixtureIdentityMapping(
            [
                VerifiedCustomerMapping(
                    source_id="known", shopify_customer_id="100", shop_key=store.shop_key
                )
            ]
        )
        reader = Reader(provider)
        before = db.scalar(select(func.sum(CommerceEntry.net_micros)))
        for _ in range(2):
            result = preview(
                db, store.workspace_id, provider, cid, 1, store.id, reader, mapping, NOW
            )
            key = identity_key(Vault(configuration), store, "customer", "100")
            assert list(result["customers"]) == [key]
            assert result["customers"][key][0]["email_status"] == "subscribed"
            assert result["unresolved_profiles"] == 1
            assert result["persisted"] is False and result["sales_contribution"] == "none"
        assert db.scalar(select(func.sum(CommerceEntry.net_micros))) == before == 90_000_000
        assert db.scalar(select(func.count()).select_from(CommerceOrder)) == 1
        with pytest.raises(HTTPException):
            preview(db, store.workspace_id + 100, provider, cid, 1, store.id, reader, mapping, NOW)
        with pytest.raises(HTTPException, match="generation"):
            preview(db, store.workspace_id, provider, cid, 2, store.id, reader, mapping, NOW)
        integration.status = "revoked"
        db.flush()
        with pytest.raises(HTTPException, match="connection unavailable"):
            preview(db, store.workspace_id, provider, cid, 1, store.id, reader, mapping, NOW)
        integration.status = "active"
        db.flush()
        reader.repeated = True
        with pytest.raises(HTTPException, match="repeated"):
            preview(db, store.workspace_id, provider, cid, 1, store.id, reader, mapping, NOW)
        reader.repeated = False
        db.add(
            CommerceSuppression(
                workspace_id=store.workspace_id,
                shop_key=store.shop_key,
                kind="customer",
                object_key=key,
            )
        )
        db.flush()
        with pytest.raises(HTTPException, match="privacy"):
            preview(db, store.workspace_id, provider, cid, 1, store.id, reader, mapping, NOW)


class IO:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def get(self, path: str, headers: dict[str, str], params: dict[str, str]) -> dict[str, Any]:
        self.calls.append((path, headers, params))
        return self.response


def test_fixed_profile_reads_project_out_personal_and_revenue_fields() -> None:
    cases: list[tuple[CustomerProvider, dict[str, Any], str]] = [
        (
            "klaviyo",
            {
                "data": [
                    {
                        "id": "a",
                        "attributes": {
                            "email": "private@example.test",
                            "subscriptions": {"email": {"marketing": {"consent": "SUBSCRIBED"}}},
                            "properties": {"revenue": 999},
                        },
                    }
                ],
                "links": {"next": "https://a.klaviyo.com/api/profiles/?page%5Bcursor%5D=next"},
            },
            "subscribed",
        ),
        (
            "hubspot",
            {
                "results": [
                    {
                        "id": "b",
                        "properties": {
                            "lifecyclestage": "customer",
                            "email": "private@example.test",
                            "revenue": 999,
                        },
                    }
                ],
                "paging": {"next": {"after": "next", "link": "https://untrusted.invalid"}},
            },
            "unknown",
        ),
        (
            "omnisend",
            {
                "data": [
                    {
                        "id": "c",
                        "identifiers": [
                            {
                                "id": "private@example.test",
                                "channels": {"email": {"status": "subscribed"}},
                            }
                        ],
                        "customProperties": {"revenue": 999},
                    }
                ],
                "paging": {"cursors": {"after": "next"}},
            },
            "subscribed",
        ),
    ]
    for provider, payload, email in cases:
        io = IO(payload)
        reader = ProfileReader(provider, io)
        page = reader.page("fixture", "synthetic", None, NOW)
        assert page.profiles[0].email_status == email
        assert page.next_cursor == "next"
        assert "private@" not in page.model_dump_json()
        assert "revenue" not in page.model_dump_json()
        reader.page("fixture", "synthetic", page.next_cursor, NOW)
        assert io.calls[1][0] == io.calls[0][0]
        assert "untrusted" not in io.calls[1][0]
    bad = IO({"data": [], "links": {"next": "https://untrusted.invalid/?page[cursor]=x"}})
    with pytest.raises(ValueError, match="untrusted"):
        ProfileReader("klaviyo", bad).page("fixture", "synthetic", None, NOW)


def test_conflicting_channels_and_custom_lifecycle_stay_unknown() -> None:
    page = ProfileReader(
        "omnisend",
        IO(
            {
                "data": [
                    {
                        "id": "a",
                        "identifiers": [
                            {"channels": {"email": {"status": "subscribed"}}},
                            {"channels": {"email": {"status": "unsubscribed"}}},
                        ],
                    }
                ]
            }
        ),
    ).page("fixture", "synthetic", None, NOW)
    assert page.profiles[0].email_status == "unknown"
    page = ProfileReader(
        "hubspot",
        IO({"results": [{"id": "a", "properties": {"lifecyclestage": "custom-sensitive-label"}}]}),
    ).page("fixture", "synthetic", None, NOW)
    assert page.profiles[0].lifecycle == "unknown"
