"""Concrete native MockHTTP + persisted reporting/Shopify evidence; no ready bundles."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.service import manifest
from app.collectors import account_diagnostics
from app.commerce.models import CommerceStore
from app.customers.models import CustomerSession
from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault as GoogleVault
from app.lifecycle.privacy import workspace_export_revision
from app.meta.models import MetaConnection
from app.meta.security import Vault as MetaVault
from app.planning_documents.common import fingerprint
from app.planning_documents.context import AccountRef, PlanInputRevision
from app.planning_documents.evidence_adapter import OwnedPlanningEvidenceReader
from app.planning_documents.evidence_local import recheck_local_sources, resolve_source_fences
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.publication import customer_intents
from app.settings import Settings, settings
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from app.workspaces.models import WorkspaceIntegration
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.goal_progress_fixture import ready
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_google_native_inventory import key, payloads
from tests.test_meta_native_inventory import PRIVATE
from tests.test_meta_native_inventory import Server as MetaServer
from tests.test_shopify_sales import configuration as configuration
from tests.test_tiktok_native_inventory import Server as TikTokServer

pytestmark = pytest.mark.planning_boundary


def setup_evidence(
    engine: Engine, config: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch, platform: str
) -> Any:
    for attr in (
        "google_customer_encryption_key",
        "meta_token_encryption_key",
        "source_token_encryption_key",
    ):
        monkeypatch.setattr(settings, attr, SecretStr(Fernet.generate_key().decode()))
    monkeypatch.setattr(settings, "google_customer_client_id", "synthetic-client")
    monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("synthetic-secret"))
    monkeypatch.setattr(settings, "meta_client_secret", SecretStr("synthetic-app-secret"))
    monkeypatch.setattr(settings, "customer_native_diagnostics_enabled", True)
    _, provider, wid, gid, _, _, principal, _ = ready(engine, config, replicas)
    now = datetime.now(UTC)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=1)
    with Session(engine) as db:
        integration = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="native",
            provider=platform,
            display_name="Native",
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        external = "1234567890" if platform == "google_ads" else "123"
        account = AdvertisingAccount(
            workspace_id=wid,
            connection_id=integration.id,
            platform=AdvertisingPlatform(platform),
            external_account_id=external,
            name="Native",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(account)
        db.flush()
        sid = uuid4().hex
        native: Any
        bundle = dict(access_token=PRIVATE, expires_at=(now + timedelta(hours=1)).isoformat())
        if platform == "google_ads":
            native = GoogleCustomerConnection(
                id=sid,
                workspace_id=wid,
                integration_id=integration.id,
                account_id=account.id,
                external_account_id=external,
                encrypted_grant=GoogleVault().seal(wid, sid, "synthetic-refresh"),
                backfill_through=start.date(),
                history_floor=start.date(),
                window_start=start.date(),
                window_end=start.date(),
                last_sync_at=now,
            )
            query = "google.v25.campaign-day.metrics-conversions.v1"
        elif platform == "meta_ads":
            native = MetaConnection(
                workspace_id=wid,
                workspace_integration_id=integration.id,
                account_id=account.id,
                external_account_id=external,
                encrypted_credentials=MetaVault(settings).seal(wid, external, bundle),
                covered_from=start.date(),
                covered_through=start.date(),
                last_sync_at=now,
                conversion_action_type="purchase",
            )
            from app.meta.security import API_VERSION

            query = f"meta.{API_VERSION}.campaign-day.v1"
        else:
            native = SourceConnection(
                id=sid,
                workspace_id=wid,
                integration_id=integration.id,
                account_id=account.id,
                provider=platform,
                external_id=external,
                status="connected",
                generation=1,
                window_start=start.date(),
                window_end=start.date(),
                encrypted_grant=SourceVault().seal(wid, platform, sid, bundle),
                covered_from=start.date(),
                covered_through=start.date(),
                last_sync_at=now,
            )
            query = "tiktok.v1.3.basic-campaign-day.generic-conversion.v1"
        db.add(native)
        campaign = Campaign(
            account_id=account.id,
            platform=account.platform,
            external_campaign_id="1" if platform == "google_ads" else "5",
            name="Campaign",
        )
        db.add(campaign)
        db.flush()
        metric = DailyMetric(
            platform=account.platform,
            metric_date=start.date(),
            entity_type="campaign",
            entity_id=campaign.id,
            campaign_id=campaign.id,
            impressions=100,
            clicks=10,
            cost_micros=100_000_000,
            conversions=Decimal("2"),
            conversion_value_micros=200_000_000,
        )
        db.add(metric)
        db.flush()
        digest, rows = manifest(db, account, start.date(), start.date())
        privacy = workspace_export_revision(db, wid)
        completion = PerformanceCompletion(
            id=uuid4().hex,
            workspace_id=wid,
            account_id=account.id,
            platform=platform,
            source_connection_ref=str(native.id),
            generation=native.generation,
            privacy_revision=privacy,
            starts_on=start.date(),
            ends_on=start.date(),
            currency="USD",
            time_zone="UTC",
            query_version=query,
            semantics="explicit_platform_event"
            if platform == "meta_ads"
            else "provider_aggregate_unspecified",
            selected_event="purchase" if platform == "meta_ads" else None,
            reporting_basis="provider_defaults_unspecified",
            completed_at=now,
            row_count=len(rows),
            manifest_digest=digest,
        )
        db.add(completion)
        db.flush()
        db.add(
            CurrentPerformance(account_id=account.id, workspace_id=wid, completion_id=completion.id)
        )
        db.commit()
        scope = customer_intents.account(db, wid, account.id)
        ref = AccountRef(
            workspace_id=wid,
            account_id=account.id,
            connection_id=integration.id,
            platform=platform,
            connection_version=scope.connection_version,
        )
        goal = goals.owned(db, wid, gid)
        definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
        inputs = PlanInputRevision(
            workspace_id=wid,
            plan_id=uuid4().hex,
            revision=1,
            goal=dict(
                workspace_id=wid,
                goal_id=gid,
                revision=goal.revision,
                definition=definition,
                definition_digest=fingerprint(
                    "goal-definition", definition.model_dump(mode="json")
                ),
                confirmation_reference=goal.confirmed_preview_id,
            ),
            accounts=(ref,),
            budget_period=dict(
                starts_on=definition.budget_start,
                ends_on_exclusive=definition.budget_end,
                currency=definition.target_window.currency,
                time_zone=definition.target_window.time_zone,
            ),
            total_ceiling_micros=definition.budget_micros,
            aggressiveness=definition.aggressiveness,
            reporting_window=dict(starts_at=start, ends_at_exclusive=end),
            comparison_window=None,
            milestone="Grow sales",
            product_offer=None,
            constraints=(),
            assumptions=(),
            excluded_entity_keys=(),
            fixed_allocations=(),
            scenario_intents=(),
            created_by=principal.user.id,
            created_at=now,
        )
        policy = PlanningCompositionPolicy(version="1", generator_version="1")
        ticket = GenerationTicket(
            operation_id=uuid4().hex,
            actor_id=principal.user.id,
            session_digest=principal.session.digest,
            inputs=inputs,
            expected_version=0,
            expected_parent_digest=None,
            privacy_revision=privacy,
            sources=resolve_source_fences(db, principal=principal, accounts=(ref,), now=now),
            policy_version=policy.version,
            policy_digest=policy.digest(),
            prepared_at=now,
        )
    server = MetaServer() if platform == "meta_ads" else TikTokServer()
    calls = []

    def wire(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.host)
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200, json=dict(access_token=PRIVATE, token_type="Bearer", expires_in=3600)
            )
        query = json.loads(req.content).get("query", "") if platform == "google_ads" else ""
        fields = req.url.params.get("fields", "")
        meta = (
            ".name" in query
            or "name" in fields.split(",")
            or "campaign_name" in fields
            or "adgroup_name" in fields
        )
        if platform == "google_ads":
            data: Any = payloads()
            data["customer"][0]["customer"]["timeZone"] = "UTC"
            if "FROM ad_group" in query:
                return httpx.Response(200, json={"results": []})
            rows = data["campaign"] if meta else data[key(query)]
            if meta:
                for row in rows:
                    row["campaign"]["name"] = "Owned Campaign"
            return httpx.Response(200, json={"results": rows})
        if meta and isinstance(server, MetaServer):
            data = {"data": server.adsets if req.url.path.endswith("adsets") else server.campaigns}
        else:
            data = server(req).json()
        if meta:
            for row in data["data"] if platform == "meta_ads" else data["data"]["list"]:
                row[
                    "name"
                    if platform == "meta_ads"
                    else "adgroup_name"
                    if "adgroup/get" in req.url.path
                    else "campaign_name"
                ] = "Owned Name"
        return httpx.Response(200, json=data)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    reader = OwnedPlanningEvidenceReader(
        lambda: Session(engine),
        principal=principal,
        provider=provider,
        policy=policy,
        clock=lambda: datetime.now(UTC),
    )
    return reader, ticket, principal, calls


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_real_sources_and_final_recheck(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    reader, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    bundle = reader.collect(ticket)
    assert calls and len(bundle.catalogs) == len(bundle.performance) == 1
    assert bundle.commerce and bundle.commerce.document.net_sales_micros == -10_000_000
    assert bundle.performance[0].conversion_qualification == (
        "reported_only" if platform == "meta_ads" else "unavailable"
    )
    if platform == "tiktok_ads":
        assert bundle.performance[0].document.conversions is None
    with Session(customer_engine) as db:
        recheck_local_sources(
            db, principal=principal, ticket=ticket, bundle=bundle, now=datetime.now(UTC)
        )


@pytest.mark.parametrize(
    "change",
    [
        "metric",
        "completion",
        "session",
        "goal",
        "commerce",
        "watermark",
        "native_id",
        "privacy",
        "expiry",
        "source",
        "import",
        "currency",
    ],
)
def test_final_source_changes_abort(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    reader, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    bundle = reader.collect(ticket)
    with Session(customer_engine) as db:
        row: Any
        if change == "metric":
            row = db.scalar(
                select(DailyMetric).where(
                    DailyMetric.campaign_id == bundle.performance[0].document.campaign_id
                )
            )
            assert row
            row.clicks += 1
        elif change == "completion":
            row = db.scalar(select(CurrentPerformance))
            assert row
            db.delete(row)
        elif change == "session":
            row = db.get(CustomerSession, ticket.session_digest)
            assert row
            row.revoked_at = 1
        elif change == "goal":
            row = goals.owned(db, ticket.inputs.workspace_id, ticket.inputs.goal.goal_id)
            row.confirmed_preview_id = None
        elif change in {"commerce", "watermark"}:
            row = db.get(CommerceStore, ticket.inputs.goal.definition.store_id)
            assert row
            if change == "commerce":
                row.revision += 1
            else:
                row.last_sync_at = datetime.now(UTC)
        elif change == "privacy":
            from app.lifecycle.privacy import advance_workspace_export_revision

            advance_workspace_export_revision(db, ticket.inputs.workspace_id)
        elif change == "source":
            row = db.scalar(
                select(MetaConnection).where(
                    MetaConnection.account_id == ticket.inputs.accounts[0].account_id
                )
            )
            assert row
            row.generation += 1
        elif change == "import":
            row = db.get(CommerceStore, ticket.inputs.goal.definition.store_id)
            assert row
            row.window_end = datetime.now(UTC)
        elif change == "currency":
            row = db.get(AdvertisingAccount, ticket.inputs.accounts[0].account_id)
            assert row
            row.currency_code = "EUR"
        elif change == "expiry":
            pass
        else:
            row = db.get(Campaign, bundle.performance[0].document.campaign_id)
            assert row
            row.external_campaign_id = "999"
        db.commit()
    with Session(customer_engine) as db, pytest.raises(HTTPException):
        recheck_local_sources(
            db,
            principal=principal,
            ticket=ticket,
            bundle=bundle,
            now=datetime.now(UTC) + (timedelta(minutes=6) if change == "expiry" else timedelta()),
        )


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_default_zero_is_not_qualified(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    reader, ticket, _, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    with Session(customer_engine) as db:
        account = db.get(AdvertisingAccount, ticket.inputs.accounts[0].account_id)
        assert account
        campaign = db.scalar(select(Campaign).where(Campaign.account_id == account.id))
        assert campaign
        metric = db.scalar(select(DailyMetric).where(DailyMetric.campaign_id == campaign.id))
        assert metric
        metric.conversions = Decimal(0)
        metric.conversion_value_micros = 0
        db.flush()
        current = db.get(CurrentPerformance, account.id)
        assert current
        completion = db.get(PerformanceCompletion, current.completion_id)
        assert completion
        completion.manifest_digest, _ = manifest(
            db, account, completion.starts_on, completion.ends_on
        )
        db.commit()
    bundle = reader.collect(ticket)
    assert bundle.performance[0].conversion_qualification == "unavailable"
    assert "goal_conversion_unqualified" in bundle.performance[0].reasons


@pytest.mark.parametrize("change", ["http", "revoke", "generation"])
@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_ambiguous_read_failure_aborts(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    change: str,
) -> None:
    reader, ticket, _, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    original = account_diagnostics.diagnostic_transport()
    fired = False

    def fail(req: httpx.Request) -> httpx.Response:
        nonlocal fired
        if change == "http":
            return httpx.Response(503, json={"error": "unavailable"})
        result = original.handle_request(req)
        if not fired:
            fired = True
            with Session(customer_engine) as db:
                if change == "revoke":
                    session = db.get(CustomerSession, ticket.session_digest)
                    assert session
                    session.revoked_at = 1
                else:
                    model: Any = {
                        "google_ads": GoogleCustomerConnection,
                        "meta_ads": MetaConnection,
                        "tiktok_ads": SourceConnection,
                    }[platform]
                    row = db.scalar(
                        select(model).where(
                            model.account_id == ticket.inputs.accounts[0].account_id
                        )
                    )
                    assert row
                    row.generation += 1
                db.commit()
        return result

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(fail)
    )
    from app.collectors.google_native_inventory import GoogleNativeInventoryUnavailable
    from app.collectors.meta_native_inventory import MetaNativeInventoryUnavailable
    from app.collectors.tiktok_native_inventory import TikTokNativeInventoryUnavailable
    from app.google_connections.http import GoogleReadError

    with pytest.raises(
        (
            HTTPException,
            GoogleNativeInventoryUnavailable,
            MetaNativeInventoryUnavailable,
            TikTokNativeInventoryUnavailable,
            GoogleReadError,
        )
    ):
        reader.collect(ticket)


@pytest.mark.parametrize("missing", ["completion", "rows", "window"])
def test_explicit_reporting_gaps_are_not_zero(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    reader, ticket, _, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    with Session(customer_engine) as db:
        account = db.get(AdvertisingAccount, ticket.inputs.accounts[0].account_id)
        assert account
        current = db.get(CurrentPerformance, account.id)
        assert current
        if missing == "completion":
            db.delete(current)
        elif missing == "rows":
            rows = list(
                db.scalars(
                    select(DailyMetric)
                    .join(Campaign, Campaign.id == DailyMetric.campaign_id)
                    .where(Campaign.account_id == account.id)
                )
            )
            for row in rows:
                db.delete(row)
            db.flush()
            completion = db.get(PerformanceCompletion, current.completion_id)
            assert completion
            completion.manifest_digest, empty = manifest(
                db, account, completion.starts_on, completion.ends_on
            )
            completion.row_count = len(empty)
        db.commit()
    if missing == "window":
        old = ticket.inputs.reporting_window
        window = old.model_copy(
            update={
                "starts_at": old.starts_at - timedelta(days=1),
                "ends_at_exclusive": old.ends_at_exclusive - timedelta(days=1),
            }
        )
        ticket = ticket.model_copy(
            update={"inputs": ticket.inputs.model_copy(update={"reporting_window": window})}
        )
    result = reader.collect(ticket)
    if missing == "rows":
        assert result.performance[0].document.conversions is None
        assert result.performance[0].document.spend_micros is None
        assert result.performance[0].completeness == "unavailable"
    else:
        assert not result.performance
        assert any(g.section == "reported_metrics" for g in result.gaps)


def test_owned_missing_commerce_history_is_unavailable_not_zero(
    customer_engine: Engine, configuration: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    with Session(customer_engine) as db:
        store = db.get(CommerceStore, ticket.inputs.goal.definition.store_id)
        assert store
        store.last_sync_at = None
        db.commit()
    bundle = reader.collect(ticket)
    assert bundle.commerce and bundle.commerce.document.net_sales_micros is None
    assert bundle.commerce.document.reasons == ("missing_history",)
    with Session(customer_engine) as db:
        store = db.get(CommerceStore, ticket.inputs.goal.definition.store_id)
        assert store
        store.last_sync_at = datetime.now(UTC)
        db.commit()
    with Session(customer_engine) as db, pytest.raises(HTTPException):
        recheck_local_sources(
            db, principal=principal, ticket=ticket, bundle=bundle, now=datetime.now(UTC)
        )


@pytest.mark.parametrize("change", [None, "metric", "replacement", "matching_window"])
def test_mismatched_reporting_pin_final_races(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str | None,
) -> None:
    reader, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    old = ticket.inputs.reporting_window
    window = old.model_copy(
        update={
            "starts_at": old.starts_at - timedelta(days=1),
            "ends_at_exclusive": old.ends_at_exclusive - timedelta(days=1),
        }
    )
    ticket = ticket.model_copy(
        update={"inputs": ticket.inputs.model_copy(update={"reporting_window": window})}
    )
    bundle = reader.collect(ticket)
    assert not bundle.performance
    gap = next(g for g in bundle.gaps if g.reason == "reporting_window_mismatch")
    assert gap.reporting_pin is not None
    with Session(customer_engine) as db:
        pin = gap.reporting_pin
        current = db.get(CurrentPerformance, ticket.inputs.accounts[0].account_id)
        assert current
        completion = db.get(PerformanceCompletion, pin.completion_id)
        assert completion
        if change == "metric":
            metric = db.scalar(
                select(DailyMetric).where(DailyMetric.campaign_id == pin.campaign_id)
            )
            assert metric
            metric.clicks += 1
        elif change == "replacement":
            values = {
                c.name: getattr(completion, c.name) for c in PerformanceCompletion.__table__.columns
            }
            values["id"] = uuid4().hex
            replacement = PerformanceCompletion(**values)
            db.add(replacement)
            db.flush()
            current.completion_id = replacement.id
        elif change == "matching_window":
            completion.starts_on = window.starts_at.date()
            completion.ends_on = window.starts_at.date()
            source = db.scalar(
                select(MetaConnection).where(MetaConnection.account_id == current.account_id)
            )
            assert source
            source.covered_from = source.covered_through = completion.starts_on
            account = db.get(AdvertisingAccount, current.account_id)
            assert account
            completion.manifest_digest, rows = manifest(
                db, account, completion.starts_on, completion.ends_on
            )
            completion.row_count = len(rows)
        db.commit()
    with Session(customer_engine) as db:
        if change is None:
            recheck_local_sources(
                db, principal=principal, ticket=ticket, bundle=bundle, now=datetime.now(UTC)
            )
        else:
            with pytest.raises(HTTPException):
                recheck_local_sources(
                    db, principal=principal, ticket=ticket, bundle=bundle, now=datetime.now(UTC)
                )
