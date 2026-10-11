"""Actual owned reporting and private image ports, not ready bundles or live traffic."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from app.ads.models import Campaign, DailyMetric
from app.billing.models import WorkspaceBilling
from app.campaign_review.models import MediaObject
from app.campaign_review.service import upload
from app.campaign_review.storage import LocalMediaStore
from app.customers.models import CustomerMembership, CustomerSession
from app.goals.models import Goal
from app.lifecycle.privacy import bump_workspace_export_revision
from app.planning_documents import creative_paired_reader as module
from app.planning_documents.creative_basis import CreativeInputV1, PlanningMediaSelectionV1
from app.planning_documents.creative_basis_reader import OwnedPlanningImageReader
from app.planning_documents.creative_finalization import recheck_collected_creative
from app.planning_documents.models import PlanInputRow, PlanRequestRow, PlanRow, PlanVersionRow
from app.planning_documents.policy_capabilities import reporting_capability
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.read_context import PlanningReadContexts
from app.planning_documents.selected_paired_reader import OwnedSelectedPairedReader
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from tests.q16_clock_feasibility_probe import paid
from tests.selected_range_plan_fixture import prepared_range_plan
from tests.test_campaign_review import png
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration


def prepared(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    path: Path,
    *,
    platform: str = "google_ads",
    empty: bool = False,
) -> Any:
    if platform == "google_ads":
        old, ticket, _, _, _ = prepared_range_plan(engine, config, replicas, patch)
        principal, provider = old.principal, old.provider
    else:
        _, ticket, principal, _ = setup_evidence(engine, config, replicas, patch, platform)
        provider = replicas[2]
        ticket = GenerationTicket.model_validate(
            ticket.model_copy(
                update={"inputs": ticket.inputs.model_copy(update={"selected_reporting": ()})}
            )
        )
    paid(engine, ticket.inputs.workspace_id, datetime.now(UTC), patch)
    store = LocalMediaStore(path)
    with Session(engine) as db:
        media = upload(
            db, ticket.inputs.workspace_id, principal.user.id, png(), store, datetime.now(UTC)
        )
        mid = media.id
        requested = CreativeInputV1(
            media_selections=()
            if empty
            else (PlanningMediaSelectionV1(media_id=media.id, expected_sha256=media.sha256),)
        )
    policy = PlanningCompositionPolicy(
        version="inlet.descriptive-review.v5", generator_version="inlet.descriptive-planning.v5"
    )
    ticket = GenerationTicket.model_validate(
        {
            **ticket.model_dump(),
            "inputs": {**ticket.inputs.model_dump(), "creative": requested},
            "policy_version": policy.version,
            "policy_digest": policy.digest(),
        }
    )
    sessions: list[Session] = []
    calls: list[str] = []

    def session() -> Session:
        db = Session(engine)
        sessions.append(db)
        return db

    original = store.read_exact

    def read(*args: Any) -> bytes:
        assert all(not db.in_transaction() for db in sessions)
        calls.append("bytes")
        return original(*args)

    patch.setattr(store, "read_exact", read)
    active = provider.check_active

    def identity(*args: Any) -> None:
        assert all(not db.in_transaction() for db in sessions)
        calls.append("identity")
        active(*args)

    patch.setattr(provider, "check_active", identity)
    reader = module.OwnedCreativePairedReader(
        session,
        principal=principal,
        provider=provider,
        policy=policy,
        store=store,
        clock=lambda: datetime.now(UTC),
    )
    return reader, ticket, mid, calls


def plan_counts(engine: Engine) -> tuple[int, ...]:
    with Session(engine) as db:
        return tuple(
            db.scalar(select(func.count()).select_from(model)) or 0
            for model in (PlanRow, PlanInputRow, PlanVersionRow, PlanRequestRow)
        )


@pytest.mark.parametrize(
    "platform,empty",
    [("google_ads", False), ("google_ads", True), ("meta_ads", False), ("tiktok_ads", False)],
)
def test_owned_ports_retain_original_context_no_persistence(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    empty: bool,
) -> None:
    reader, ticket, _, calls = prepared(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        platform=platform,
        empty=empty,
    )
    before = plan_counts(customer_engine)
    result = reader.collect(ticket)
    result.assert_ticket(ticket)
    assert plan_counts(customer_engine) == before
    assert result.creative.ticket_digest == ticket.digest()
    assert result.creative.basis.requested == ticket.inputs.creative
    assert len(result.creative.rows) == (0 if empty else 1)
    assert calls.count("bytes") == (0 if empty else 1)
    context = {x.reference.kind: x.document for x in result.reporting.selected.context}
    assert context == {"customer_context": ticket.inputs, "planning_policy": reader.policy}
    if platform == "google_ads":
        assert len(result.reporting.traffic) == 2
        assert len(result.reporting.selected.performance) == 2
    else:
        assert not result.reporting.selected.performance
        assert {g.reason for g in result.reporting.selected.window_gaps} == {
            "unsupported_selected_mapping"
        }
    assert (
        reporting_capability(reader.policy.version, reader.policy.generator_version).mode
        == "creative_selected_requested_window"
    )


@pytest.mark.parametrize(
    "change", ["reporting", "image_after", "session", "membership", "goal", "paid", "privacy"]
)
def test_change_between_collections_rejected(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change: str,
) -> None:
    reader, ticket, mid, _ = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    before = plan_counts(customer_engine)

    def mutate() -> None:
        with Session(customer_engine) as db, db.begin():
            if change == "reporting":
                db.execute(
                    update(DailyMetric)
                    .where(
                        DailyMetric.campaign_id.in_(
                            select(Campaign.id).where(
                                Campaign.account_id == ticket.inputs.accounts[0].account_id
                            )
                        )
                    )
                    .values(clicks=101)
                )
            elif change == "image_after":
                db.execute(update(MediaObject).where(MediaObject.id == mid).values(width=3))
            elif change == "session":
                db.execute(
                    update(CustomerSession)
                    .where(CustomerSession.digest == ticket.session_digest)
                    .values(revoked_at=1)
                )
            elif change == "membership":
                db.execute(
                    update(CustomerMembership)
                    .where(CustomerMembership.user_id == ticket.actor_id)
                    .values(role="viewer")
                )
            elif change == "goal":
                db.execute(
                    update(Goal)
                    .where(Goal.id == ticket.inputs.goal.goal_id)
                    .values(confirmed_preview_id=None)
                )
            elif change == "paid":
                db.execute(
                    update(WorkspaceBilling)
                    .where(WorkspaceBilling.workspace_id == ticket.inputs.workspace_id)
                    .values(status="canceled")
                )
            else:
                bump_workspace_export_revision(db, ticket.inputs.workspace_id)

    if change == "image_after":
        original = OwnedPlanningImageReader.collect_pinned

        def collect(self: Any, *args: Any) -> Any:
            result = original(self, *args)
            mutate()
            return result

        monkeypatch.setattr(OwnedPlanningImageReader, "collect_pinned", collect)
    else:
        original_read = reader.store.read_exact

        def read(*args: Any) -> bytes:
            data = original_read(*args)
            mutate()
            return cast(bytes, data)

        monkeypatch.setattr(reader.store, "read_exact", read)
    with pytest.raises((HTTPException, ValueError)):
        reader.collect(ticket)
    assert plan_counts(customer_engine) == before


def test_invalid_context_denied_before_any_io(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    reader, ticket, _, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path, platform="meta_ads"
    )
    for changes in (
        {"session_digest": "f" * 64},
        {"actor_id": "f" * 32},
        {"policy_digest": "0" * 64},
        {"inputs": ticket.inputs.model_copy(update={"creative": None})},
        {"inputs": ticket.inputs.model_copy(update={"selected_reporting": None})},
    ):
        with pytest.raises((HTTPException, ValueError)):
            reader.collect(ticket.model_copy(update=changes))
        assert not calls
    original = reader.policy
    for changes in (
        {"generator_version": "inlet.descriptive-planning.v4"},
        {"native_writes": "available"},
    ):
        reader.policy = original.model_copy(update=changes)
        with pytest.raises((HTTPException, ValueError)):
            reader.collect(ticket)
        assert not calls


@pytest.mark.parametrize("mode", ["expired", "backwards", "naive", "callback_error"])
def test_final_context_exit_freshness(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str,
) -> None:
    reader, ticket, _, _ = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path, platform="meta_ads"
    )
    completed = [False]
    exited = [False]
    deadline: list[datetime] = []
    original_collect = OwnedSelectedPairedReader.collect

    def reporting(self: Any, *args: Any) -> Any:
        result = original_collect(self, *args)
        deadline.append(min(c.reference.expires_at for c in result.selected.catalogs))
        return result

    monkeypatch.setattr(OwnedSelectedPairedReader, "collect", reporting)
    original_recheck = recheck_collected_creative

    def recheck(*args: Any, **kwargs: Any) -> Any:
        result = original_recheck(*args, **kwargs)
        completed[0] = True
        return result

    monkeypatch.setattr(module, "recheck_collected_creative", recheck)
    original_open = PlanningReadContexts.open

    @contextmanager
    def opened(self: Any) -> Iterator[Session]:
        with original_open(self) as db:
            yield db
        if completed[0]:
            exited[0] = True

    monkeypatch.setattr(PlanningReadContexts, "open", opened)
    failure = ValueError("unexpected clock callback")

    def clock() -> datetime:
        if not exited[0]:
            return datetime.now(UTC)
        if mode == "callback_error":
            raise failure
        return cast(
            datetime,
            {
                "expired": deadline[0],
                "backwards": ticket.prepared_at - timedelta(seconds=1),
                "naive": datetime.now(),
            }[mode],
        )

    reader.clock = clock
    with pytest.raises((HTTPException, ValueError)) as error:
        reader.collect(ticket)
    assert exited[0]
    if mode == "callback_error":
        assert error.value is failure


@pytest.mark.parametrize("damage", ["proof", "reporting_after_creative"])
def test_final_creative_proof_and_second_reporting_check(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    damage: str,
) -> None:
    reader, ticket, _, _ = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path, platform="meta_ads"
    )
    with Session(customer_engine) as db:
        before = tuple(db.scalars(select(DailyMetric.clicks).order_by(DailyMetric.id)))
    entered = [False]

    def recheck(db: Session, **kwargs: Any) -> Any:
        proof = recheck_collected_creative(db, **kwargs)
        entered[0] = True
        if damage == "proof":
            return proof.model_copy(
                update={
                    "images": (
                        proof.images[0].model_copy(update={"row_identity_digest": "0" * 64}),
                    )
                }
            )
        db.execute(
            update(DailyMetric)
            .where(
                DailyMetric.campaign_id.in_(
                    select(Campaign.id).where(
                        Campaign.account_id == ticket.inputs.accounts[0].account_id
                    )
                )
            )
            .values(clicks=999)
        )
        return proof

    monkeypatch.setattr(module, "recheck_collected_creative", recheck)
    with pytest.raises((HTTPException, ValueError)):
        reader.collect(ticket)
    assert entered[0]
    with Session(customer_engine) as db:
        assert tuple(db.scalars(select(DailyMetric.clicks).order_by(DailyMetric.id))) == before


@pytest.mark.parametrize("damage", ["provider_error", "storage_error", "input_hash"])
def test_unexpected_errors_and_wrong_requested_image(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    damage: str,
) -> None:
    reader, ticket, _, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path, platform="meta_ads"
    )
    failure = RuntimeError("unexpected injected callback")

    def fail(*args: Any) -> Any:
        raise failure

    if damage == "provider_error":
        monkeypatch.setattr(reader.provider, "check_active", fail)
    elif damage == "storage_error":
        monkeypatch.setattr(reader.store, "read_exact", fail)
    else:
        creative = ticket.inputs.creative
        ticket = ticket.model_copy(
            update={
                "inputs": ticket.inputs.model_copy(
                    update={
                        "creative": creative.model_copy(
                            update={
                                "media_selections": (
                                    creative.media_selections[0].model_copy(
                                        update={"expected_sha256": "0" * 64}
                                    ),
                                )
                            }
                        ),
                    }
                )
            }
        )
    with pytest.raises((RuntimeError, ValueError)) as error:
        reader.collect(ticket)
    if damage == "input_hash":
        assert "bytes" not in calls
    else:
        assert error.value is failure
