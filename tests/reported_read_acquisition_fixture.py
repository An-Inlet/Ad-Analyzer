"""Current GET acquisition over one authentic retained effect; no ready data seeded."""

import base64
import io
import json
from datetime import date, datetime, timedelta
from typing import Any, NamedTuple
from urllib.parse import parse_qs, urlsplit

import pytest
from app.customers.access import CustomerPrincipal
from app.meta import client as wire
from app.meta.models import MetaConnection
from app.meta.security import API_VERSION, Vault, utc
from app.meta.sync import MetaSyncService
from app.reported_feedback.contracts import ReportedAcquisitionRequestV1
from app.reported_feedback.models import ReportedFeedbackJob
from app.reported_feedback.runtime import ReportedFeedbackRuntime
from app.settings import Settings
from pydantic import SecretStr
from sqlalchemy.orm import Session

from tests.reported_original_fixture import PreparedReportedRead, RetainedReportedOriginalIds
from tests.test_meta_connection import campaign, insight, page


class PreparedReportedAcquisition(NamedTuple):
    workspace_id: int
    principal: CustomerPrincipal
    runtime: ReportedFeedbackRuntime
    job: ReportedFeedbackJob
    request: ReportedAcquisitionRequestV1
    source: MetaConnection
    clock: list[datetime]
    runner: MetaSyncService
    requests: list[tuple[str, dict[str, list[str]]]]
    control: dict[str, Any]
    original: RetainedReportedOriginalIds


def prepare_reported_acquisition(
    db: Session,
    config: Settings,
    prepared: PreparedReportedRead,
    monkeypatch: pytest.MonkeyPatch,
) -> PreparedReportedAcquisition:
    wid, principal, _, runtime, _, progress, clock, original = prepared
    config = config.model_copy(
        update={
            "meta_enabled": True,
            "meta_client_id": "100000000000001",
            "meta_client_secret": SecretStr("offline-secret-" * 3),
            "meta_token_encryption_key": SecretStr(base64.urlsafe_b64encode(b"m" * 32).decode()),
            "meta_redirect_uri": "https://example.test/dashboard/meta/callback",
        }
    )
    job = db.get(ReportedFeedbackJob, progress.id)
    assert job is not None
    assert (
        job.workspace_id,
        job.account_id,
        job.campaign_id,
        job.original_attempt_id,
        job.original_actor_id,
        job.original_session_digest,
    ) == (
        original.workspace_id,
        original.account_id,
        original.campaign_id,
        original.attempt_id,
        original.actor_id,
        original.session_digest,
    )
    assert job.completed_observations == 0 and job.state == "pending"
    request = ReportedAcquisitionRequestV1.model_validate(job.document)
    clock[0] = max(clock[0], utc(job.next_due_at) + timedelta(seconds=1))
    source = db.get(MetaConnection, job.source_connection_id)
    assert source is not None
    assert (source.id, source.workspace_id, source.account_id) == (
        original.source_id,
        original.workspace_id,
        original.account_id,
    )
    assert request.anchor.source_connection_id == source.id
    assert request.anchor.source_generation == source.generation
    assert request.anchor.external_account_id == source.external_account_id
    assert request.anchor.external_campaign_id == "5"
    assert request.anchor.original_attempt_id == original.attempt_id
    assert clock[0].timestamp() < principal.session.expires_at
    assert clock[0] < request.expires_at
    source.encrypted_credentials = Vault(config).seal(
        wid,
        source.external_account_id,
        {
            "access_token": "offline-report-token",
            "expires_at": (clock[0] + timedelta(days=90)).isoformat(),
        },
    )
    db.commit()
    external_account_id = source.external_account_id
    requests: list[tuple[str, dict[str, list[str]]]] = []
    control: dict[str, Any] = {"missing": False, "zero": False, "revision": 0}

    class Opener:
        def open(self, outgoing: Any, timeout: int) -> io.BytesIO:
            assert set(control) <= {
                "missing",
                "zero",
                "revision",
                "before_conversions",
                "after_conversions",
                "on_insights",
            }
            parsed = urlsplit(outgoing.full_url)
            assert parsed.hostname == "graph.facebook.com" and outgoing.method == "GET"
            assert timeout == 12
            query = parse_qs(parsed.query)
            requests.append((parsed.path, query))
            if parsed.path == f"/{API_VERSION}/act_{external_account_id}/campaigns":
                payload = page(campaign("5", external_account_id))
            elif parsed.path == f"/{API_VERSION}/act_{external_account_id}/adsets":
                payload = page()
            else:
                assert parsed.path == f"/{API_VERSION}/act_{external_account_id}/insights"
                assert query["level"] == ["campaign"]
                window = json.loads(query["time_range"][0])
                start, end = (
                    date.fromisoformat(window["since"]),
                    date.fromisoformat(window["until"]),
                )
                days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
                if control["missing"]:
                    days = days[:-1]
                conversions = control.get(
                    "before_conversions"
                    if start == request.before.starts_on
                    else "after_conversions",
                    "3",
                )
                payload = page(
                    *[
                        insight(
                            account_id=external_account_id,
                            campaign_id="5",
                            date_start=d.isoformat(),
                            date_stop=d.isoformat(),
                            spend="0" if control["zero"] else str(10 + control["revision"]),
                            actions=[]
                            if control["zero"]
                            else [{"action_type": "purchase", "value": str(conversions)}],
                            action_values=[]
                            if control["zero"]
                            else [{"action_type": "purchase", "value": "30"}],
                        )
                        for d in days
                    ]
                )
                if control.get("on_insights"):
                    control["on_insights"]()
            return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(wire, "build_opener", lambda *_: Opener())
    runner = MetaSyncService(db, config, reported_feedback=runtime)
    return PreparedReportedAcquisition(
        wid, principal, runtime, job, request, source, clock, runner, requests, control, original
    )
