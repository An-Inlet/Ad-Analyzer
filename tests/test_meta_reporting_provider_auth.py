"""Actual composed route refuses provider authentication and expired owned grants."""

from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.campaign_performance.selected_models import SelectedCaptureRow, SelectedFactRow
from app.meta.models import MetaConnection
from app.meta.security import Vault
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.meta_reporting_assembly_fixture import Assembly
from tests.test_meta_customer_flow import configuration as configuration
from tests.test_meta_customer_flow import customer_engine as customer_engine
from tests.test_meta_customer_flow import meta as meta
from tests.test_meta_customer_flow import replicas as replicas


@pytest.mark.parametrize("mode", ["http_401", "expired_grant"])
def test_provider_auth_refusal(meta: Any, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    f = meta
    a = Assembly(f, monkeypatch)
    if mode == "expired_grant":
        with Session(f.engine) as db:
            source = db.scalar(select(MetaConnection).where(MetaConnection.account_id == f.aid))
            assert source
            vault = Vault(f.config)
            bundle = vault.open(f.wid, "123", source.encrypted_credentials)
            bundle["expires_at"] = (f.now - timedelta(days=1)).isoformat()
            source.encrypted_credentials = vault.seal(f.wid, "123", bundle)
            db.commit()
    else:

        def refused(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            f.calls.append(request.url.path)
            return httpx.Response(401, json={"error": "synthetic_meta_auth_refusal"})

        monkeypatch.setattr(f, "wire", refused)
    intent = f.selected()
    result = a.post("/captures", intent)
    assert result.status_code == 409 and result.json() == {"detail": "meta_reporting_unavailable"}
    assert len(a.constructed) == len(a.closed) == 1
    assert len(f.calls) == (1 if mode == "http_401" else 0)
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 0
        assert db.scalar(select(func.count()).select_from(SelectedFactRow)) == 0
