"""Fixture-backed Meta customer acquisition through retained plans on both SQL engines."""

import json
from pathlib import Path
from typing import Any

import pytest
from app.campaign_performance.selected_models import (
    EventSelectionRow,
    SelectedCaptureRow,
    SelectedFactRow,
)
from app.planning_documents.documents import PlanVersion
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.meta_customer_fixture import MetaFixture
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture
def meta(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> MetaFixture:
    return MetaFixture(customer_engine, configuration, replicas, monkeypatch, tmp_path / "basis")


@pytest.mark.parametrize("value", ["10", "0", None])
def test_capture_saved_plan_history_export_and_replay(
    meta: MetaFixture, value: str | None, tmp_path: Path
) -> None:
    f = meta
    f.value = value
    intent = f.selected()
    response = f.post("/captures", intent)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert receipt["returned_rows"] == 61 and receipt["missing_count_rows"] == (
        61 if value is None else 0
    )
    assert receipt["explicit_zero_rows"] == (61 if value == "0" else 60 if value == "10" else 0)
    assert (
        receipt["monetary_value"] == "unsupported" and receipt["effective_attribution"] == "unknown"
    )
    calls = len(f.calls)
    assert f.post("/captures", intent).json() == receipt and len(f.calls) == calls
    f.body["inputs"]["selected_reporting"] = [
        dict(account_id=f.aid, capture_id=receipt["capture_id"])
    ]
    root = f"/api/customer/v1/workspaces/{f.wid}/planning/plans"
    created = f.alice.post(root, headers=headers(f.alice), json=f.body)
    assert created.status_code == 201, created.text
    path = root + "/" + created.json()["plan_id"]
    generate = dict(
        expected_input_revision=1, expected_version=0, request_key="meta-count-customer-plan"
    )
    generated = f.alice.post(path + "/generate", headers=headers(f.alice), json=generate)
    assert generated.status_code == 200, generated.text
    document = PlanVersion.model_validate(generated.json()["document"])
    assert document.schema_version == "inlet.plan-version.v3"
    assert document.selected_reporting_proof is not None
    pin = next(a.capture_pin for a in document.selected_reporting_proof.accounts if a.capture_pin)
    assert pin.observation_provenance is not None
    assert pin.observation_provenance.settings is not None
    assert (
        pin.observation_provenance.settings.profile == "meta.website-purchase-count.campaign-day.v1"
    )
    assert pin.observation_provenance.attribution.report_time_basis == "unknown"
    observations = [e for e in document.evidence if e.kind == "reported_metrics"]
    assert observations and all(
        e.document_schema == "inlet.selected-plan-window.v1" for e in observations
    )
    assert all(e.coverage == ("unavailable" if value is None else "partial") for e in observations)
    assert all("attribution_unavailable" in e.reasons for e in observations)
    rationale = " ".join(action.rationale for action in document.actions)
    assert f"selected count {value if value is not None else 'unavailable'} (" in rationale
    assert "Clicks and spend unavailable" in rationale
    assert "unsupported_selected_mapping" not in rationale
    assert document.advertising_writes_enabled is False and document.spending_authority == "none"
    artifacts = {"capture": receipt, "generated": generated.json()}
    for key, suffix in [
        ("current", ""),
        ("history", "/versions/1"),
        ("export", "/export?version=1"),
    ]:
        result = f.alice.get(path + suffix)
        assert result.status_code == 200, result.text
        saved = PlanVersion.model_validate(result.json()["document"])
        assert saved.digest() == document.digest()
        artifacts[key] = result.json()
    replay = f.alice.post(path + "/generate", headers=headers(f.alice), json=generate)
    assert replay.status_code == 200 and replay.json()["document_digest"] == document.digest()
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 1
        assert db.scalar(select(func.count()).select_from(SelectedFactRow)) == 61
    (tmp_path / "meta-customer-plan-artifacts.json").write_text(json.dumps(artifacts, indent=2))


@pytest.mark.parametrize(
    "attack", ["dates", "grant", "foreign", "csrf", "head", "session", "final"]
)
def test_selection_and_capture_boundaries(
    meta: MetaFixture, attack: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = meta
    intent = f.selected()
    if attack == "dates":
        intent["starts_on"] = "2026-08-02"
    elif attack == "grant":
        from app.meta.models import MetaConnection
        from app.meta.security import Vault

        with Session(f.engine) as db:
            source = db.scalar(select(MetaConnection))
            assert source
            source.encrypted_credentials = Vault(f.config).seal(
                f.wid,
                "123",
                {"access_token": "offline-replacement", "expires_at": f.now.isoformat()},
            )
            db.commit()
    elif attack == "head":
        intent["expected_selection_digest"] = "f" * 64
    elif attack == "session":
        from app.customers.access import SESSION_COOKIE, digest
        from app.customers.models import CustomerSession

        with Session(f.engine) as db:
            session = db.get(CustomerSession, digest(f.alice.cookies[SESSION_COOKIE]))
            assert session
            session.revoked_at = int(f.now.timestamp())
            db.commit()
    elif attack == "final":
        from app.planning_documents.read_context import PlanningReadContexts
        from fastapi import HTTPException

        actual = PlanningReadContexts.authorize
        checks = []

        def fail(self: Any, db: Session, wid: int, actor: str) -> None:
            actual(self, db, wid, actor)
            if db.scalar(select(func.count()).select_from(SelectedCaptureRow)):
                checks.append(1)
                if len(checks) == 3:
                    raise HTTPException(401, "offline final refusal")

        monkeypatch.setattr(PlanningReadContexts, "authorize", fail)
    if attack == "csrf":
        response = f.alice.post(f.root + "/captures", json=intent)
    else:
        response = f.post("/captures", intent, f.bob if attack == "foreign" else None)
    assert response.status_code in {401, 403, 404, 409}, response.text
    if attack == "final":
        assert checks == [1, 1, 1] and len(f.calls) == 2
    else:
        assert not f.calls
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 0
        assert db.scalar(select(func.count()).select_from(SelectedFactRow)) == 0


def test_confirmation_rollback_and_unconfigured_invalidation(
    meta: MetaFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.customer_meta_reporting import get_meta_reporting_runtime
    from app.planning_documents.read_context import PlanningReadContexts
    from fastapi import HTTPException

    f = meta
    basis = f.reviewed()
    actual = PlanningReadContexts.authorize
    seen = []

    def fail(self: Any, db: Session, wid: int, actor: str) -> None:
        actual(self, db, wid, actor)
        if db.scalar(select(func.count()).select_from(EventSelectionRow)):
            seen.append(1)
            raise HTTPException(401, "offline confirmation failure")

    with monkeypatch.context() as patch:
        patch.setattr(PlanningReadContexts, "authorize", fail)
        failed = f.post(
            "/event-selection",
            dict(
                **basis,
                option_id=basis["basis_digest"],
                expected_selection_id=None,
                expected_selection_digest=None,
            ),
        )
        assert failed.status_code == 401 and seen
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(EventSelectionRow)) == 0
    intent = f.selected()
    f.alice.app.dependency_overrides[get_meta_reporting_runtime] = lambda: None
    assert f.post("/captures", intent).status_code == 503
    invalid = f.post(
        "/event-selection/invalidate",
        {
            k: intent[k]
            for k in ("account_id", "expected_selection_id", "expected_selection_digest")
        },
    )
    assert invalid.status_code == 200 and invalid.json()["state"] == "refresh_required"
    f.alice.app.dependency_overrides[get_meta_reporting_runtime] = lambda: f.runtime
    assert (
        f.post(
            "/available-range",
            dict(
                account_id=f.aid,
                request_id="a" * 32,
                requested_starts_on="2026-08-01",
                requested_ends_on="2026-09-30",
            ),
        ).status_code
        == 409
    )


def test_capture_commitment_rejects_new_basis_old_id_and_new_session(meta: MetaFixture) -> None:
    from app.meta.models import MetaConnection
    from app.meta.security import Vault

    from tests.test_customer_identity import login

    f = meta
    intent = f.selected()
    first = f.post("/captures", intent)
    assert first.status_code == 200, first.text
    calls = len(f.calls)
    with Session(f.engine) as db:
        source = db.scalar(select(MetaConnection))
        assert source
        vault = Vault(f.config)
        original = vault.open(f.wid, "123", source.encrypted_credentials)
        source.encrypted_credentials = vault.seal(f.wid, "123", original)
        db.commit()
    reviewed = f.reviewed()
    changed = {**intent, "basis_digest": reviewed["basis_digest"]}
    assert changed["basis_digest"] != intent["basis_digest"]
    assert f.post("/captures", changed).status_code == 409
    prepared = f.post("/capture-intents", {k: v for k, v in changed.items() if k != "request_id"})
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["request_id"] != intent["request_id"]
    assert (
        f.post("/captures", {**prepared.json(), "request_id": intent["request_id"]}).status_code
        == 409
    )
    # Actual same-customer replacement session must not reuse a prior signed intent.
    login(f.alice, "q16-owner:replacement")
    assert f.post("/captures", prepared.json()).status_code == 409
    assert len(f.calls) == calls
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 1
