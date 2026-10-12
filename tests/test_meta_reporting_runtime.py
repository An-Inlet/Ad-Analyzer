"""Disabled defaults, exact read transport and actual app runtime boundaries."""

from typing import Any

import httpx
import pytest
from app.campaign_performance.selected_models import SelectedCaptureRow, SelectedFactRow
from app.meta import selected_runtime
from app.settings import Settings, settings
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.meta_reporting_assembly_fixture import Assembly
from tests.test_meta_customer_flow import configuration as configuration
from tests.test_meta_customer_flow import customer_engine as customer_engine
from tests.test_meta_customer_flow import meta as meta
from tests.test_meta_customer_flow import replicas as replicas


def test_disabled_default_never_constructs_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings.model_fields["customer_meta_reporting_enabled"].default is False
    monkeypatch.setattr(settings, "customer_meta_reporting_enabled", False)
    monkeypatch.setattr(
        selected_runtime, "network_transport", lambda: pytest.fail("network constructed")
    )
    assert selected_runtime.configured_runtime() is None
    with pytest.raises(ValueError, match="unavailable"):
        selected_runtime.CountReadTransport(settings)


@pytest.mark.parametrize(
    "mode",
    [
        "disabled",
        "secret",
        "key",
        "invalid_key",
        "unauthenticated",
        "provider",
        "midread",
        "final",
        "replay_disabled",
    ],
)
def test_actual_app_runtime_failures(meta: Any, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    a = Assembly(meta, monkeypatch)
    f = meta
    intent = f.selected()
    if mode == "disabled":
        monkeypatch.setattr(settings, "customer_meta_reporting_enabled", False)
    elif mode == "secret":
        monkeypatch.setattr(settings, "meta_client_secret", None)
    elif mode == "key":
        monkeypatch.setattr(settings, "meta_token_encryption_key", None)
    elif mode == "invalid_key":
        monkeypatch.setattr(settings, "meta_token_encryption_key", SecretStr("invalid-offline-key"))
    elif mode == "unauthenticated":
        a.alice.cookies.clear()
    elif mode == "provider":
        f.provider.fail = True
    elif mode == "midread":
        f.hook = lambda: monkeypatch.setattr(settings, "customer_meta_reporting_enabled", False)
    elif mode == "final":
        from app.planning_documents.read_context import PlanningReadContexts

        original = PlanningReadContexts.authorize
        checkpoints = []

        def disable(self: Any, db: Session, wid: int, actor: str) -> None:
            original(self, db, wid, actor)
            if db.scalar(select(func.count()).select_from(SelectedCaptureRow)):
                checkpoints.append(1)
                if len(checkpoints) == 3:
                    monkeypatch.setattr(settings, "customer_meta_reporting_enabled", False)

        monkeypatch.setattr(PlanningReadContexts, "authorize", disable)
    else:
        assert a.post("/captures", intent).status_code == 200
        monkeypatch.setattr(settings, "customer_meta_reporting_enabled", False)
    response = a.post("/captures", intent)
    assert response.status_code in {401, 403, 409, 503}, response.text
    assert len(a.constructed) == (1 if mode in {"midread", "final", "replay_disabled"} else 0)
    assert len(a.closed) == len(a.constructed)
    if mode == "final":
        assert checkpoints == [1, 1, 1]
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == (
            1 if mode == "replay_disabled" else 0
        )
        assert db.scalar(select(func.count()).select_from(SelectedFactRow)) == (
            61 if mode == "replay_disabled" else 0
        )
    if mode in {"disabled", "secret", "key", "invalid_key"}:
        assert (
            a.post(
                "/event-selection/invalidate",
                {
                    k: intent[k]
                    for k in ("account_id", "expected_selection_id", "expected_selection_digest")
                },
            ).status_code
            == 200
        )


@pytest.mark.parametrize(
    "method,url",
    [
        ("POST", "https://graph.facebook.com/v26.0/act_123/insights"),
        ("GET", "http://graph.facebook.com/v26.0/act_123/insights"),
        ("GET", "https://example.test/v26.0/act_123/insights"),
        ("GET", "https://graph.facebook.com/v26.0/act_123/campaigns"),
        ("DELETE", "https://graph.facebook.com/v26.0/act_123"),
    ],
    ids=["post", "http", "foreign", "path", "delete"],
)
def test_transport_rejects_other_paths(
    monkeypatch: pytest.MonkeyPatch, method: str, url: str
) -> None:
    monkeypatch.setattr(selected_runtime, "available", lambda _: True)
    monkeypatch.setattr(
        selected_runtime,
        "network_transport",
        lambda: httpx.MockTransport(lambda _: pytest.fail("forbidden provider request")),
    )
    with (
        selected_runtime.CountReadTransport(settings) as transport,
        pytest.raises(ValueError, match="unavailable"),
    ):
        transport.handle_request(httpx.Request(method, url))


def test_confirmation_disabled_at_final_authority(
    meta: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.campaign_performance.selected_models import EventSelectionRow
    from app.planning_documents.read_context import PlanningReadContexts

    a = Assembly(meta, monkeypatch)
    basis = meta.reviewed()
    actual = PlanningReadContexts.authorize
    checkpoints = []

    def disable(self: Any, db: Session, wid: int, actor: str) -> None:
        actual(self, db, wid, actor)
        if db.scalar(select(func.count()).select_from(EventSelectionRow)):
            checkpoints.append(1)
            if len(checkpoints) == 2:
                monkeypatch.setattr(settings, "customer_meta_reporting_enabled", False)

    monkeypatch.setattr(PlanningReadContexts, "authorize", disable)
    result = a.post(
        "/event-selection",
        dict(
            **basis,
            option_id=basis["basis_digest"],
            expected_selection_id=None,
            expected_selection_digest=None,
        ),
    )
    assert result.status_code == 503 and checkpoints == [1, 1]
    assert not a.constructed
    with Session(meta.engine) as db:
        assert db.scalar(select(func.count()).select_from(EventSelectionRow)) == 0
