"""Private configured v5 actual HTTP journeys; no live provider or ad writes."""

import re
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow, PlanVersionRow
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionRun
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.creative_runtime_fixture import configured
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_selected_runtime_api import create
from tests.test_shopify_sales import configuration as configuration


def generation() -> dict[str, Any]:
    return dict(expected_input_revision=1, expected_version=0, request_key="creative-v5-generate")


@pytest.mark.parametrize(
    "platform,images",
    [
        ("google_ads", 0),
        ("google_ads", 1),
        ("google_ads", 2),
        ("meta_ads", 1),
        ("tiktok_ads", 1),
    ],
)
def test_owned_input_upload_generation_graph_and_replay(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    images: int,
) -> None:
    f, root, body, calls, _, store = configured(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        platform=platform,
        images=images,
    )
    byte_reads: list[int] = []
    original = store.read_exact

    def read(*args: Any) -> bytes:
        byte_reads.append(1)
        return cast(bytes, original(*args))

    monkeypatch.setattr(store, "read_exact", read)
    url = create(f, root, body)
    assert byte_reads == []  # Admission proves metadata scope, not byte inspection.
    response = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert response.status_code == 200, response.text
    saved = response.json()
    doc = PlanVersion.model_validate(saved["document"])
    assert doc.policy_version == "inlet.descriptive-review.v5"
    assert doc.creative_proof is not None and doc.creative_composition is not None
    basis = doc.creative_proof.basis
    assert len(basis.images) == images and len(byte_reads) == images
    assert basis.requested.model_dump(mode="json") == body["inputs"]["creative"]
    assert all(image.visual_assessment == "not_assessed" for image in basis.images)
    assert doc.creative_composition.basis_digest == basis.digest()
    if platform == "google_ads":
        rationale = doc.actions[0].rationale.split("Comparison")[0]
        assert "100 observed clicks" in rationale and "100 USD observed spend" in rationale
        count = re.search(r"selected count ([0-9.]+) \(", rationale)
        assert count is not None and Decimal(count.group(1)) == Decimal(10)
        assert "Observed zero selected conversions" not in rationale
    else:
        proposals = doc.creative_composition.proposals
        assert len(proposals) == 1
        assert proposals[0].production.deliverable_status == "production_required"
        assert proposals[0].production.visual_assessment == "not_assessed"
        assert len(proposals[0].production.storyboard) == (3 if platform == "tiktok_ads" else 0)
        assert "unsupported_selected_mapping" in doc.model_dump_json()
    observed = [(image.media_id, image.observed_at) for image in basis.images]
    before = len(calls), len(f.calls), len(byte_reads)
    replay = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert replay.status_code == 200 and replay.json() == saved
    assert (len(calls), len(f.calls), len(byte_reads)) == before
    current = f.alice.get(url)
    assert current.status_code == 200 and current.json()["freshness"] == "current", current.text
    assert current.json()["document"] == saved["document"]
    assert f.alice.get(url + "/versions/1").json()["document"] == saved["document"]
    exported = f.alice.get(url + "/export?version=1")
    assert exported.status_code == 200 and exported.json()["document"] == saved["document"]
    lookup = f.alice.get(root + "/requests/generate/creative-v5-generate")
    assert lookup.status_code == 200 and lookup.json() == saved
    exported_document = PlanVersion.model_validate(exported.json()["document"])
    assert exported_document.creative_proof is not None
    assert [
        (image.media_id, image.observed_at)
        for image in exported_document.creative_proof.basis.images
    ] == observed
    assert (len(calls), len(f.calls), len(byte_reads)) == before
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 1
        kinds = list(db.scalars(select(PlanDependencyRow.kind)))
        assert kinds.count("local_creative_basis_v1") == 1
        assert kinds.count("creative_basis") == 1
        assert kinds.count("local_reporting_v3") == 1
        for model in (ProviderExecutionRun, ProviderExecutionAttempt):
            assert db.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("damage", ["media_after_read", "reporting_during_read", "flush_expiry"])
def test_actual_generation_failure_is_atomic(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    damage: str,
) -> None:
    from app.ads.models import Campaign, DailyMetric
    from app.campaign_review.models import MediaObject
    from app.lifecycle.privacy import database_utc_now
    from app.planning_documents import repository
    from app.planning_documents.models import PlanRequestRow, PlanRow
    from sqlalchemy import update

    f, root, body, _, _, store = configured(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
    )
    url = create(f, root, body)
    original_read = store.read_exact
    expires: list[Any] = []
    mutations: list[str] = []
    original_flush = Session.flush

    def read(*args: Any) -> bytes:
        result = original_read(*args)
        with Session(customer_engine) as db, db.begin():
            if damage == "media_after_read":
                db.execute(
                    update(MediaObject).where(MediaObject.workspace_id == f.wid).values(width=3)
                )
            elif damage == "reporting_during_read":
                db.execute(
                    update(DailyMetric)
                    .where(
                        DailyMetric.campaign_id.in_(
                            select(Campaign.id).where(Campaign.account_id == f.aid)
                        )
                    )
                    .values(clicks=DailyMetric.clicks + 1)
                )
        mutations.append(damage)
        return cast(bytes, result)

    def flush(db: Session, *args: Any, **kwargs: Any) -> None:
        pending = [row.valid_until for row in db.new if isinstance(row, PlanVersionRow)]
        original_flush(db, *args, **kwargs)
        expires.extend(pending)

    if damage == "flush_expiry":
        monkeypatch.setattr(Session, "flush", flush)
        monkeypatch.setattr(
            repository,
            "database_utc_now",
            lambda db: expires[0] if expires else database_utc_now(db),
        )
    else:
        monkeypatch.setattr(store, "read_exact", read)
    response = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert response.status_code == 409, response.text
    if damage == "flush_expiry":
        assert expires
        assert response.json()["detail"] == "generation evidence expired"
    else:
        assert mutations == [damage]
        expected = (
            "current campaign reporting evidence unavailable"
            if damage == "reporting_during_read"
            else "creative planning evidence unavailable"
        )
        assert response.json()["detail"] == expected
    with Session(customer_engine) as db:
        for model in (PlanVersionRow, PlanDependencyRow):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(PlanRequestRow)
                .where(PlanRequestRow.operation == "generate")
            )
            == 0
        )
        assert (
            db.scalar(select(PlanRow.version_head).where(PlanRow.id == url.rsplit("/", 1)[1])) == 0
        )


def test_actual_input_final_save_rejects_media_changed_after_prepare(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.campaign_review.models import MediaObject
    from app.planning_documents import input_resolution
    from app.planning_documents.models import PlanInputRow, PlanRequestRow, PlanRow
    from sqlalchemy import update

    f, root, body, _, _, _ = configured(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
    )
    original = input_resolution.resolve
    resolutions: list[int] = []
    mutated = False

    def resolve(*args: Any, **kwargs: Any) -> Any:
        nonlocal mutated
        result = original(*args, **kwargs)
        resolutions.append(1)
        # Catalog resolution also invokes this function while preparation locks are held.
        # The second invocation is the actual gap after that transaction commits.
        if len(resolutions) != 2:
            return result
        with Session(customer_engine) as db, db.begin():
            db.execute(
                update(MediaObject).where(MediaObject.workspace_id == f.wid).values(sha256="f" * 64)
            )
        mutated = True
        return result

    monkeypatch.setattr(input_resolution, "resolve", resolve)
    response = f.alice.post(root, headers=headers(f.alice), json=body)
    assert response.status_code == 409, response.text
    assert len(resolutions) == 2 and mutated
    assert response.json()["detail"] == "selected creative media unavailable"
    with Session(customer_engine) as db:
        for model in (PlanRow, PlanInputRow, PlanVersionRow, PlanDependencyRow, PlanRequestRow):
            assert db.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("boundary", ["provider", "clock"])
def test_actual_collection_preserves_unexpected_callback_error(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    boundary: str,
) -> None:
    from datetime import UTC, datetime

    from app.api import customer_planning_documents as api
    from app.planning_documents.models import PlanRequestRow, PlanRow

    f, root, body, _, _, store = configured(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
    )
    url = create(f, root, body)
    error = ValueError("unexpected injected callback defect")
    observed = False
    original_read = store.read_exact
    original_active = f.provider.check_active

    def read(*args: Any) -> bytes:
        nonlocal observed
        result = original_read(*args)
        observed = True
        return cast(bytes, result)

    def active(*args: Any) -> None:
        if observed and boundary == "provider":
            raise error
        original_active(*args)

    def clock() -> datetime:
        if observed and boundary == "clock":
            raise error
        return datetime.now(UTC)

    monkeypatch.setattr(store, "read_exact", read)
    monkeypatch.setattr(f.provider, "check_active", active)
    monkeypatch.setattr(api, "utc_now", clock)
    with pytest.raises(ValueError) as caught:
        f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert observed and caught.value is error
    with Session(customer_engine) as db:
        for model in (PlanVersionRow, PlanDependencyRow):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(PlanRequestRow)
                .where(PlanRequestRow.operation == "generate")
            )
            == 0
        )
        assert (
            db.scalar(select(PlanRow.version_head).where(PlanRow.id == url.rsplit("/", 1)[1])) == 0
        )


def test_actual_bundle_rejects_structurally_valid_backdated_candidate(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.planning_documents.creative_plan_composer import CreativePlanComposer
    from app.planning_documents.models import PlanRequestRow, PlanRow

    f, root, body, _, _, _ = configured(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        images=0,
    )
    url = create(f, root, body)
    original = CreativePlanComposer.compose

    def compose(self: CreativePlanComposer, **kwargs: Any) -> PlanVersion:
        document = original(self, **kwargs)
        ticket, bundle = kwargs["ticket"], kwargs["evidence"]
        stamp = ticket.prepared_at
        assert stamp < bundle.reporting.selected.collected_at
        # Negative fault injection changes only the candidate's timestamp claims.
        # Its actual collected envelope, retained proof, digests and source rows stay real.
        # Clamp candidate reference timestamps so structural DTO validation is not the gate.
        candidate = document.model_copy(
            update={
                "generated_at": stamp,
                "evidence": tuple(
                    ref.model_copy(
                        update={
                            "observed_at": min(ref.observed_at, stamp),
                            "observation_started_at": min(ref.observation_started_at, stamp),
                        }
                    )
                    for ref in document.evidence
                ),
            }
        )
        return PlanVersion.model_validate(candidate)

    monkeypatch.setattr(CreativePlanComposer, "compose", compose)
    response = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "candidate generation predates original creative collection"
    with Session(customer_engine) as db:
        for model in (PlanVersionRow, PlanDependencyRow):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(PlanRequestRow)
                .where(PlanRequestRow.operation == "generate")
            )
            == 0
        )
        assert (
            db.scalar(select(PlanRow.version_head).where(PlanRow.id == url.rsplit("/", 1)[1])) == 0
        )
