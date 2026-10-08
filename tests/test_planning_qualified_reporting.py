"""Owned SQL sidecars through real reporting and customer planning APIs; no Meta import claim."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.api import customer_planning_documents as api
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_contracts import (
    ReportedMetricPresenceV1,
    ReportingSemanticsV1,
    presence_digest,
)
from app.campaign_performance.presence_models import MetricPresenceRow, ReportingSemanticsRow
from app.campaign_performance.presence_report import (
    CampaignPerformanceV3,
    PresenceReadContext,
    read_current_with_presence,
)
from app.campaign_performance.presence_storage import read_presence, store_presence
from app.campaign_performance.service import manifest, read_current
from app.planning_documents.evidence_local import local_authority
from app.planning_documents.models import PlanDependencyRow
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def install_presence(
    engine: Engine, account_id: int, state: str = "positive", *, extra_campaign: bool = False
) -> tuple[ReportingSemanticsV1, tuple[ReportedMetricPresenceV1, ...]]:
    with Session(engine) as db:
        account = db.get(AdvertisingAccount, account_id)
        current = db.get(CurrentPerformance, account_id)
        assert account and current
        old = db.get(PerformanceCompletion, current.completion_id)
        assert old
        row = db.scalars(select(DailyMetric)).one()
        row.clicks, row.conversions = 100, Decimal(10 if state == "positive" else 0)
        db.flush()
        extra = None
        if extra_campaign:
            extra = Campaign(
                account_id=account_id,
                platform="meta_ads",
                external_campaign_id="6",
                name="Other Campaign",
            )
            db.add(extra)
            db.flush()
            copied = {
                key: getattr(row, key)
                for key in (
                    "platform",
                    "metric_date",
                    "entity_type",
                    "impressions",
                    "clicks",
                    "cost_micros",
                    "conversions",
                    "conversion_value_micros",
                )
            }
            db.add(DailyMetric(**copied, campaign_id=extra.id, entity_id=extra.id))
            db.flush()
        digest, legacy_rows = manifest(db, account, old.starts_on, old.ends_on)
        values = {c.name: getattr(old, c.name) for c in PerformanceCompletion.__table__.columns}
        values.update(id=uuid4().hex, manifest_digest=digest, row_count=len(legacy_rows))
        completion = PerformanceCompletion(**values)
        db.add(completion)
        db.flush()
        current.completion_id = completion.id
        db.flush()
        fact = ReportedMetricPresenceV1(
            completion_id=completion.id,
            workspace_id=account.workspace_id,
            account_id=account.id,
            campaign_id=row.campaign_id,
            native_campaign_id="5",
            metric_date=row.metric_date,
            impressions=dict(presence="present", value=row.impressions),
            clicks=dict(presence="present", value=100),
            spend_micros=dict(presence="present", value=row.cost_micros),
            selected_conversions=dict(
                presence="missing" if state == "missing" else "present",
                value=None if state == "missing" else row.conversions,
            ),
            selected_value_micros=dict(presence="missing", value=None),
        )
        facts = (
            (fact,)
            if extra is None
            else (
                fact,
                ReportedMetricPresenceV1.model_validate(
                    fact.model_copy(update={"campaign_id": extra.id, "native_campaign_id": "6"})
                ),
            )
        )
        header = ReportingSemanticsV1(
            workspace_id=account.workspace_id,
            account_id=account.id,
            connection_id=account.connection_id,
            platform="meta_ads",
            source_connection_ref=completion.source_connection_ref,
            generation=completion.generation,
            privacy_revision=completion.privacy_revision,
            completion_id=completion.id,
            legacy_manifest_digest=digest,
            producer_contract="meta.fixture-presence.v1",
            query_descriptor=completion.query_version,
            requested_starts_on=completion.starts_on,
            requested_ends_on=completion.ends_on,
            actual_starts_on=completion.starts_on,
            actual_ends_on=completion.ends_on,
            currency=completion.currency,
            time_zone=completion.time_zone,
            selected_event=dict(
                provenance="explicit_selected", native_event_id="purchase", label=None
            ),
            attribution=dict(
                click_window_days=None,
                view_window_days=None,
                report_time_basis="unknown",
                provenance="provider_default_unknown",
                producer_contract="fixture.unknown.v1",
            ),
            pagination_complete=state != "partial",
            closed_requested_period=True,
            completed_at=completion.completed_at.replace(tzinfo=UTC),
            fact_count=len(facts),
            fact_digest=presence_digest(facts),
        )
        store_presence(db, header, facts)
        db.commit()
        return header, facts


@pytest.mark.parametrize("state", ["positive", "zero", "missing", "partial"])
def test_actual_owned_sql_to_customer_plan_and_retained_presence(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    _, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    account_id = ticket.inputs.accounts[0].account_id
    h, facts = install_presence(customer_engine, account_id, state)

    def authorize(db: Session, wid: int, actor: str) -> None:
        local_authority(db, principal, wid, actor)

    with Session(customer_engine) as db:
        legacy = read_current(
            db,
            h.workspace_id,
            principal.user.id,
            account_id,
            facts[0].campaign_id,
            h.completion_id,
            authorize,
        )
        qualified = read_current_with_presence(
            db,
            h.workspace_id,
            principal.user.id,
            account_id,
            facts[0].campaign_id,
            h.completion_id,
            authorize,
        )
        assert isinstance(qualified, CampaignPerformanceV3)
        assert qualified.legacy == legacy
        if state == "positive":
            import app.campaign_performance.presence_report as reports

            original_read = read_presence
            graph_reads = []

            def tracked(db: Session, completion: PerformanceCompletion) -> Any:
                graph_reads.append(completion.id)
                return original_read(db, completion)

            with monkeypatch.context() as patch:
                patch.setattr(reports, "read_presence", tracked)
                context = PresenceReadContext(db)
                for _ in range(2):
                    assert (
                        read_current_with_presence(
                            db,
                            h.workspace_id,
                            principal.user.id,
                            account_id,
                            facts[0].campaign_id,
                            h.completion_id,
                            authorize,
                            context=context,
                        )
                        == qualified
                    )
                assert graph_reads == [h.completion_id]
                assert context.campaigns[facts[0].campaign_id] == facts

        assert CampaignPerformanceV3.model_validate_json(qualified.model_dump_json()) == qualified
        from pydantic import ValidationError

        for broken in (
            qualified.model_copy(
                update={
                    "summary": qualified.summary.model_copy(
                        update={"selected_zero_for_requested_window": state != "zero"}
                    )
                }
            ),
            qualified.model_copy(
                update={"presence": qualified.presence.model_copy(update={"fact_count": 0})}
            ),
            qualified.model_copy(
                update={"legacy": qualified.legacy.model_copy(update={"clicks": True})}
            ),
            qualified.model_copy(
                update={"legacy": qualified.legacy.model_copy(update={"conversions": "NaN"})}
            ),
            qualified.model_copy(
                update={"legacy": qualified.legacy.model_copy(update={"currency": b"USD"})}
            ),
            qualified.model_copy(
                update={
                    "legacy": qualified.legacy.model_copy(
                        update={"completed_at": h.completed_at.timestamp()}
                    )
                }
            ),
        ):
            with pytest.raises(ValidationError):
                CampaignPerformanceV3.model_validate(broken)
        assert qualified.summary.selected_zero_for_requested_window is (state == "zero")
        assert (
            qualified.conversions is None
            if state == "missing"
            else qualified.conversions is not None
        )
        with pytest.raises(HTTPException):
            read_current_with_presence(
                db,
                h.workspace_id + 1000,
                principal.user.id,
                account_id,
                facts[0].campaign_id,
                h.completion_id,
                authorize,
            )
    alice, outsider, _ = replicas
    alice.app.include_router(api.router)
    outsider.app.include_router(api.router)
    login(outsider, "qualified-outsider:1")
    root = f"/api/customer/v1/workspaces/{h.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=create_body(ticket.inputs))
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    generated = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="presence-generate"),
    )
    assert generated.status_code == 200, generated.text
    document = generated.json()["document"]
    assert document["policy_version"] == "inlet.descriptive-review.v2"
    reasons = " ".join(a["rationale"] for a in document["actions"])
    assert "100 observed reported clicks" in reasons
    assert "100 USD observed reported spend" in reasons
    if state == "positive":
        assert "10 observed provider-reported selected conversions" in reasons
        assert "observed zero selected conversions" not in reasons
    elif state == "zero":
        assert "observed zero selected conversions across the requested window" in reasons
        assert "landing page" in reasons
    else:
        assert (
            "unavailable or partial" in reasons
            and "observed zero selected conversions" not in reasons
        )
    assert document["spending_authority"] == "none"
    assert alice.get(url).json()["freshness"] == "current"
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200, exported.text
    assert outsider.get(url).status_code == 404
    with Session(customer_engine) as db:
        witness = db.scalar(
            select(PlanDependencyRow).where(PlanDependencyRow.kind == "local_reporting_v2")
        )
        assert witness and witness.evidence_key == f"local:reporting:{account_id}"
        db.execute(delete(MetricPresenceRow))
        db.commit()
    assert alice.get(url).json()["freshness"] != "current"


@pytest.mark.parametrize("change", ["delete", "appear", "corrupt", "revoked"])
def test_collection_to_final_recheck_never_saves_changed_presence(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from app.customers.models import CustomerSession
    from app.planning_documents.evidence_adapter import OwnedPlanningEvidenceReader
    from app.planning_documents.models import PlanRequestRow, PlanVersionRow
    from sqlalchemy import func, update

    _, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    h, facts = install_presence(customer_engine, ticket.inputs.accounts[0].account_id)
    if change == "appear":
        with Session(customer_engine) as db, db.begin():
            db.execute(delete(MetricPresenceRow))
            db.execute(delete(ReportingSemanticsRow))
    original = OwnedPlanningEvidenceReader.collect

    def collect(reader: OwnedPlanningEvidenceReader, generation: Any) -> Any:
        result = original(reader, generation)
        with Session(customer_engine) as db, db.begin():
            if change == "appear":
                store_presence(db, h, facts)
            elif change == "revoked":
                db.execute(
                    update(CustomerSession)
                    .where(CustomerSession.digest == principal.session.digest)
                    .values(revoked_at=int(datetime.now(UTC).timestamp()))
                )
            else:
                db.execute(delete(MetricPresenceRow))
                if change == "delete":
                    db.execute(delete(ReportingSemanticsRow))
        return result

    monkeypatch.setattr(OwnedPlanningEvidenceReader, "collect", collect)
    alice, _, _ = replicas
    alice.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{h.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=create_body(ticket.inputs))
    assert created.status_code == 201, created.text
    response = alice.post(
        root + "/" + created.json()["plan_id"] + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="changed-presence"),
    )
    assert response.status_code == (401 if change == "revoked" else 409), response.text
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 0
        assert db.scalar(select(func.count()).select_from(PlanDependencyRow)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(PlanRequestRow)
                .where(PlanRequestRow.operation == "generate")
            )
            == 0
        )


def test_legacy_policy_history_ignores_new_presence_and_viewer_reads_db_only(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.customers.models import CustomerMembership
    from app.planning_documents.composer import LEGACY_GENERATOR_VERSION, LEGACY_POLICY_VERSION
    from app.planning_documents.ports import PlanningCompositionPolicy
    from app.planning_documents.service import PlanningDocumentService
    from sqlalchemy import update

    _, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    h, _ = install_presence(customer_engine, ticket.inputs.accounts[0].account_id)

    class LegacyService(PlanningDocumentService):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.policy = PlanningCompositionPolicy(
                version=LEGACY_POLICY_VERSION, generator_version=LEGACY_GENERATOR_VERSION
            )

    monkeypatch.setattr(api, "PlanningDocumentService", LegacyService)
    alice, _, _ = replicas
    alice.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{h.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=create_body(ticket.inputs))
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    response = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="legacy-presence"),
    )
    assert response.status_code == 200, response.text
    doc = response.json()["document"]
    assert doc["policy_version"] == LEGACY_POLICY_VERSION
    assert all(
        e["document_schema"] != "inlet.owned-campaign-performance.v3" for e in doc["evidence"]
    )
    with Session(customer_engine) as db, db.begin():
        witness = db.scalar(
            select(PlanDependencyRow).where(PlanDependencyRow.kind == "local_reporting_v1")
        )
        assert witness is not None
        db.execute(delete(MetricPresenceRow))
        db.execute(delete(ReportingSemanticsRow))
        db.execute(
            update(CustomerMembership)
            .where(CustomerMembership.user_id == principal.user.id)
            .values(role="viewer")
        )
    before = len(calls)
    current = alice.get(url)
    assert current.status_code == 200, current.text
    assert current.json()["freshness"] == "current" and current.json()["document"] == doc
    assert len(calls) == before


def test_indexed_two_campaign_graph_and_expired_transaction_context(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.campaign_performance.presence_report as reports
    from pydantic import ValidationError

    _, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    h, facts = install_presence(
        customer_engine, ticket.inputs.accounts[0].account_id, extra_campaign=True
    )
    original = read_presence
    calls = []

    def tracked(db: Session, completion: PerformanceCompletion) -> Any:
        calls.append(completion.id)
        return original(db, completion)

    monkeypatch.setattr(reports, "read_presence", tracked)

    def authorize(db: Session, wid: int, actor: str) -> None:
        local_authority(db, principal, wid, actor)

    with Session(customer_engine) as db:
        context = PresenceReadContext(db)
        for fact in facts:
            result = read_current_with_presence(
                db,
                h.workspace_id,
                principal.user.id,
                h.account_id,
                fact.campaign_id,
                h.completion_id,
                authorize,
                context=context,
            )
            assert isinstance(result, CampaignPerformanceV3)
            assert result.campaign_facts == (fact,)
            assert context.campaigns[fact.campaign_id] == (fact,)
            assert context.native_ids[fact.native_campaign_id] == fact.campaign_id
            with pytest.raises(ValidationError):
                CampaignPerformanceV3.model_validate(
                    result.model_copy(update={"native_campaign_id": "999"})
                )
            with monkeypatch.context() as patch:
                patch.setattr(reports, "MAX_DOCUMENT_BYTES", 1)
                with pytest.raises(ValidationError, match="capacity"):
                    CampaignPerformanceV3.model_validate(result)
        assert calls == [h.completion_id]
        db.rollback()
        with pytest.raises(HTTPException) as failed:
            read_current_with_presence(
                db,
                h.workspace_id,
                principal.user.id,
                h.account_id,
                facts[0].campaign_id,
                h.completion_id,
                authorize,
                context=context,
            )
        assert failed.value.status_code == 409
        assert calls == [h.completion_id]
