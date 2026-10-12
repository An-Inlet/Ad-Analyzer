"""Actual-app Google reporting runtime, no live credentials or provider traffic."""

from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.selected_models import EventSelectionRow, SelectedCaptureRow
from app.google_connections import selected_runtime
from app.google_connections.selected_customer import SelectedCustomerService
from app.settings import Settings, settings
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.google_reporting_assembly_fixture import GoogleAssembly
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture
def google(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> GoogleAssembly:
    return GoogleAssembly(customer_engine, configuration, replicas, monkeypatch, tmp_path / "basis")


def intent(f: GoogleAssembly) -> dict[str, Any]:
    return dict(
        account_id=f.aid,
        request_id=uuid4().hex,
        requested_starts_on="2026-08-01",
        requested_ends_on="2026-09-30",
    )


def selected(f: GoogleAssembly) -> dict[str, Any]:
    assert f.post("/aggregate-range", intent(f)).status_code == 200
    options = f.post("/event-options", dict(account_id=f.aid))
    assert options.status_code == 200, options.text
    return dict(
        account_id=f.aid,
        option_id=next(
            x["option_id"] for x in options.json()["options"] if x["metric_family"] == "conversions"
        ),
        expected_selection_id=None,
        expected_selection_digest=None,
    )


def counts(f: GoogleAssembly) -> tuple[int, ...]:
    with Session(f.engine) as db:
        return tuple(
            db.scalar(select(func.count()).select_from(m)) or 0
            for m in (RangeReceiptRow, EventSelectionRow, SelectedCaptureRow)
        )


def test_disabled_default(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings.model_fields["customer_google_reporting_enabled"].default is False
    monkeypatch.setattr(settings, "customer_google_reporting_enabled", False)
    monkeypatch.setattr(selected_runtime, "network_transport", lambda: pytest.fail("network"))
    assert selected_runtime.configured_runtime() is None
    with pytest.raises(ValueError, match="unavailable"):
        selected_runtime.ReportingTransport(settings).handle_request(
            httpx.Request("POST", "https://oauth2.googleapis.com/token")
        )


@pytest.mark.parametrize(
    "mode",
    [
        "disabled",
        "mode",
        "version",
        "client",
        "secret",
        "developer",
        "key",
        "invalid_key",
        "session",
        "identity",
        "http401",
        "midread",
    ],
)
def test_actual_app_refusals(
    google: GoogleAssembly, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    f = google
    mutations = {
        "disabled": ("customer_google_reporting_enabled", False),
        "mode": ("google_customer_runtime_mode", "disabled"),
        "version": ("google_customer_api_version", "v23"),
        "client": ("google_customer_client_id", ""),
        "secret": ("google_customer_client_secret", None),
        "developer": ("google_customer_developer_token", None),
        "key": ("google_customer_encryption_key", None),
        "invalid_key": ("google_customer_encryption_key", SecretStr("invalid-fixture-key")),
    }
    if mode in mutations:
        monkeypatch.setattr(settings, *mutations[mode])
    elif mode == "session":
        f.alice.cookies.clear()
    elif mode == "identity":
        f.provider.fail = True
    elif mode == "http401":
        f.provider_status = 401
    else:
        f.hook = lambda _: monkeypatch.setattr(settings, "customer_google_reporting_enabled", False)
    result = f.post("/aggregate-range", intent(f))
    assert result.status_code in {401, 409, 503}, result.text
    assert "synthetic-private" not in result.text
    assert counts(f) == (0, 0, 0)
    assert len(f.constructed) == len(f.closed)
    assert len(f.calls) == (1 if mode in {"http401", "midread"} else 0)


@pytest.mark.parametrize("stage", ["range", "selection", "capture"])
def test_disable_at_final_commit(
    google: GoogleAssembly, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    f = google
    path, body = "/aggregate-range", intent(f)
    if stage != "range":
        path, body = "/event-selection", selected(f)
    if stage == "capture":
        chosen = f.post(path, body)
        assert chosen.status_code == 200, chosen.text
        path, body = (
            "/captures",
            dict(
                account_id=f.aid,
                request_id=uuid4().hex,
                expected_selection_id=chosen.json()["selection_id"],
                expected_selection_digest=chosen.json()["selection_digest"],
                starts_on="2026-08-01",
                ends_on="2026-09-30",
            ),
        )
    before = counts(f)
    # Target the explicit final availability fence, not an earlier read guard.
    reached = []
    original_gate = SelectedCustomerService.require_runtime

    def gate(service: SelectedCustomerService) -> None:
        import inspect

        frame = inspect.currentframe()
        assert frame
        caller = frame.f_back
        assert caller
        if caller.f_code.co_name in {"acquire_range", "confirm", "acquire_selected"}:
            active = service._active
            assert active is not None
            model = {
                "range": RangeReceiptRow,
                "selection": EventSelectionRow,
                "capture": SelectedCaptureRow,
            }[stage]
            assert (
                active[0].scalar(select(func.count()).select_from(model))
                == before[["range", "selection", "capture"].index(stage)] + 1
            )
            reached.append(True)
            monkeypatch.setattr(settings, "customer_google_reporting_enabled", False)
        original_gate(service)

    monkeypatch.setattr(SelectedCustomerService, "require_runtime", gate)
    result = f.post(path, body)
    assert result.status_code == 503, result.text
    assert reached == [True] and counts(f) == before
    assert len(f.constructed) == len(f.closed)


def test_disabled_replay_and_invalidation(
    google: GoogleAssembly, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = google
    choice = selected(f)
    selected_response = f.post("/event-selection", choice)
    assert selected_response.status_code == 200
    data = selected_response.json()
    body = dict(
        account_id=f.aid,
        request_id=uuid4().hex,
        expected_selection_id=data["selection_id"],
        expected_selection_digest=data["selection_digest"],
        starts_on="2026-08-01",
        ends_on="2026-09-30",
    )
    first = f.post("/captures", body)
    assert first.status_code == 200, first.text
    n = len(f.calls)
    assert f.post("/captures", body).json() == first.json() and len(f.calls) == n
    monkeypatch.setattr(settings, "customer_google_reporting_enabled", False)
    assert f.post("/captures", body).status_code == 503 and len(f.calls) == n
    assert (
        f.post(
            "/event-selection/invalidate",
            dict(
                account_id=f.aid,
                expected_selection_id=data["selection_id"],
                expected_selection_digest=data["selection_digest"],
            ),
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "case",
    [
        "get",
        "http",
        "foreign",
        "mutate",
        "port",
        "userinfo",
        "query",
        "authorization_code",
        "duplicate_grant",
        "blank_duplicate",
        "blank_extra",
        "oversize",
    ],
)
def test_transport_refuses_non_read_requests(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    from cryptography.fernet import Fernet

    config = settings.model_copy(
        update=dict(
            customer_google_reporting_enabled=True,
            google_customer_runtime_mode="google_read",
            google_customer_api_version="v24",
            google_customer_client_id="synthetic",
            google_customer_client_secret=SecretStr("synthetic"),
            google_customer_developer_token=SecretStr("synthetic"),
            google_customer_encryption_key=SecretStr(Fernet.generate_key().decode()),
        )
    )
    monkeypatch.setattr(
        selected_runtime, "network_transport", lambda: pytest.fail("network constructed")
    )
    url = "https://googleads.googleapis.com/v24/customers/1234567890/googleAds:search"
    method = "POST"
    body = b"{}"
    if case == "get":
        method = "GET"
    elif case == "http":
        url = url.replace("https:", "http:")
    elif case == "foreign":
        url = url.replace("googleads.googleapis.com", "other.invalid")
    elif case == "mutate":
        url = url.replace("googleAds:search", "googleAds:mutate")
    elif case == "port":
        url = url.replace(".com/", ".com:8443/")
    elif case == "userinfo":
        url = url.replace("https://", "https://u@")
    elif case == "query":
        url += "?extra=1"
    else:
        url = "https://oauth2.googleapis.com/token"
        body = (
            b"client_id=a&client_secret=b&refresh_token=c&grant_type=authorization_code"
            if case == "authorization_code"
            else (
                b"client_id=a&client_secret=b&refresh_token=c&grant_type=refresh_token"
                b"&grant_type=refresh_token"
            )
        )
    if case in {"blank_duplicate", "blank_extra", "oversize"}:
        body = b"client_id=a&client_secret=b&refresh_token=c&grant_type=refresh_token"
        body += (
            b"&grant_type="
            if case == "blank_duplicate"
            else b"&extra="
            if case == "blank_extra"
            else b"x" * 65537
        )
    with pytest.raises(ValueError, match="unavailable"):
        selected_runtime.ReportingTransport(config).handle_request(
            httpx.Request(method, url, content=body)
        )
