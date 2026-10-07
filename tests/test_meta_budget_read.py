"""Real GET wire parsing and owned vault/session assembly, no financial proof mocks."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.collectors import owned_meta_budget as owned
from app.collectors.meta_budget import MetaBudgetHTTP, NativeBudgetContext, NativeBudgetUnavailable
from app.commerce.sync import CommerceSyncService
from app.goals import service as goals
from app.initial_planning.native_budget_contracts import NativeBudgetRequestV1
from app.meta.models import MetaConnection
from app.publication import customer_intents
from app.publication.contracts import fingerprint
from app.settings import Settings
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import FakeMeasurement
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_native_budget_contracts import request
from tests.test_planning_reporting_configuration import profile
from tests.test_provider_publication_contracts import NOW
from tests.test_reported_feedback_acquisition import acquisition_fixture
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_optimization_http import Server, setup


class TrackedTransport(httpx.MockTransport):
    closed = 0

    def close(self) -> None:
        self.closed += 1
        super().close()


def wire_request() -> NativeBudgetRequestV1:
    body = request().model_dump()
    body["scope"]["external_advertiser_id"] = "123"
    body["target"] = {"kind": "campaign", "external_id": "5", "campaign_id": "5"}
    return NativeBudgetRequestV1.model_validate(body)


@pytest.mark.parametrize(
    "campaign,digest",
    [
        (False, "cd8d89d97a46f0400e806ec0b8dcd77a1374edecb4515d8911a1f384e9007431"),
        (True, "f96f2ebfcfac7d585634aa43fc65c4956d3447d3e831553ed0cde56101aa4936"),
    ],
)
def test_legacy_state_bytes_keep_baseline_digest(campaign: bool, digest: str) -> None:
    # Pinned using the actual pre-extraction7767b54 parser and compared byte-for-byte.
    _, _, original, _ = setup("meta_ads", campaign=campaign)
    assert original.before.digest() == digest


@pytest.mark.parametrize(
    "change", ["daily", "lifetime", "unsupported", "cursor", "foreign", "expired", "revoked"]
)
def test_actual_get_only_collection(change: str) -> None:
    server = Server("meta_ads")
    server.meta_campaign["daily_budget"] = "5000"
    if change == "lifetime":
        server.meta_campaign.update(daily_budget="0", lifetime_budget="20000")
    if change == "unsupported":
        server.meta_campaign["is_adset_budget_sharing_enabled"] = True
    server.foreign = change == "foreign"
    requests: list[httpx.Request] = []
    clock = [NOW]

    def send(req: httpx.Request) -> httpx.Response:
        requests.append(req)
        assert req.method == "GET" and req.url.host == "graph.facebook.com"
        if change == "expired":
            clock[0] += timedelta(seconds=31)
        if change == "cursor" and req.url.path.endswith("/adsets"):
            return httpx.Response(
                200,
                json={
                    "data": [],
                    "paging": {"next": "https://foreign.invalid", "cursors": {"after": "same"}},
                },
            )
        return server(req)

    def context(req: NativeBudgetRequestV1, now: Any) -> NativeBudgetContext:
        if change == "revoked" and requests:
            raise HTTPException(401, "original customer session required")
        return NativeBudgetContext(
            request_digest=req.digest(),
            access_token=SecretStr("offline-token"),
            app_secret=None,
            expires_at=NOW + timedelta(hours=1),
            label="Owned Campaign",
        )

    transport = TrackedTransport(send)
    reader = MetaBudgetHTTP(
        context, profile().native_read, transport=transport, clock=lambda: clock[0]
    )
    assert not requests and not hasattr(reader, "apply_once")
    if change in {"cursor", "foreign", "expired", "revoked"}:
        with pytest.raises((NativeBudgetUnavailable, HTTPException)):
            reader.read(wire_request(), NOW)
    else:
        result = reader.read(wire_request(), NOW)
        assert len(requests) == 3
        if change == "unsupported":
            assert result.options == ()
        else:
            observation = result.options[0].observation
            assert observation.amount_micros == (
                200_000_000 if change == "lifetime" else 50_000_000
            )
            assert observation.budget_mode == change
            assert len(observation.budget_owner.affected_targets) == 2
            assert observation.financial_qualification == "unavailable"
    assert transport.closed == 1 and not server.posts


def test_currency_not_guessed_before_http() -> None:
    body = wire_request().model_dump()
    body["cohort"]["currency"] = "EUR"
    request_value = NativeBudgetRequestV1.model_validate(body)

    def unexpected(*args: Any) -> Any:
        raise AssertionError("unsupported currency must not perform IO")

    reader = MetaBudgetHTTP(
        unexpected,
        profile().native_read,
        transport=httpx.MockTransport(unexpected),
        clock=lambda: NOW,
    )
    with pytest.raises(NativeBudgetUnavailable, match="currency_unsupported"):
        reader.read(request_value, NOW)


@pytest.mark.parametrize("change", ["none", "revoked", "generation", "goal"])
def test_actual_owned_vault_and_original_session_after_http(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        wid, principal, _, _, acquisition, _, clock, runner, _, _, server = acquisition_fixture(
            db, configuration, tmp_path, monkeypatch
        )
        assert isinstance(server, Server)
        configuration.shopify_measurement_enabled = True
        commerce = CommerceSyncService(
            db, configuration, FakeMeasurement(configuration, [([], None)])
        )
        assert commerce.page(wid, now=clock[0])["status"] == "complete"
        db.commit()
        goal = goals.owned(db, wid, acquisition.anchor.goal_id)
        goal_digest = fingerprint(
            "inlet.optimization-goal.v1",
            {
                "definition": goals.current(db, goal).definition,
            },
        )
        scope = customer_intents.account(db, wid, acquisition.anchor.cohort.account_id)
        value = NativeBudgetRequestV1.model_validate(
            {
                "profile_digest": profile().digest(),
                "environment": "contract_test",
                "scope": scope.model_dump(),
                "cohort": acquisition.anchor.cohort.model_dump(),
                "goal_id": acquisition.anchor.goal_id,
                "goal_revision": acquisition.anchor.goal_revision,
                "goal_digest": goal_digest,
                "target": {"kind": "campaign", "external_id": "5", "campaign_id": "5"},
            }
        )
        db.rollback()
        requests: list[httpx.Request] = []
        provider = FakeProvider()

        def send(req: httpx.Request) -> httpx.Response:
            requests.append(req)
            assert req.method == "GET"
            assert req.headers["Authorization"] == "Bearer offline-report-token"
            if change == "revoked":
                provider.revoked.add(principal.user.subject)
            elif change in {"generation", "goal"}:
                with Session(customer_engine) as other:
                    if change == "generation":
                        source = other.get(MetaConnection, acquisition.anchor.source_connection_id)
                        assert source is not None
                        source.generation += 1
                    else:
                        current_goal = goals.owned(other, wid, value.goal_id)
                        current_goal.confirmed_preview_id = None
                    other.commit()
            return server(req)

        transport = TrackedTransport(send)
        monkeypatch.setattr(owned, "native_budget_transport", lambda: transport)
        with owned.owned_meta_budget_reader(
            lambda: Session(customer_engine),
            principal,
            provider,
            profile(),
            runner.settings,
            clock=lambda: clock[0],
        ) as reader:
            if change != "none":
                with pytest.raises((HTTPException, NativeBudgetUnavailable)):
                    reader.read(value, clock[0])
            else:
                result = reader.read(value, clock[0])
                assert result.options[0].observation.amount_micros == 45_000_000
        assert len(requests) == (1 if change != "none" else 3)
        assert transport.closed == 1
