"""Synthetic operator evidence on both databases; no runtime/provider activation."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import JobRun
from app.billing.models import BillingEvent, WorkspaceBilling
from app.database.session import get_db
from app.main import app
from app.mandates.models import Mandate, MandateAction
from app.operations.attention import OVERDUE_SECONDS, ROW_LIMIT, attention
from app.publication.models import PublicationPlanRecord, PublicationStepRecord
from app.settings import settings
from app.sources.models import SourceConnection
from app.workspaces.models import Workspace, WorkspaceIntegration
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)
OLD = NOW - timedelta(seconds=OVERDUE_SECONDS + 1)
PRIVATE = "private-fixture@example.invalid bearer payload 1234567890"


def workspace(db: Session, name: str, status: str = "active") -> Workspace:
    value = Workspace(slug=name, name=PRIVATE, client_name=PRIVATE, status=status)
    db.add(value)
    db.flush()
    return value


def job(db: Session, wid: int, name: str, state: JobRunStatus, started: datetime) -> None:
    db.add(
        JobRun(
            workspace_id=wid,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            job_name=name,
            status=state,
            started_at=started,
            error_message=PRIVATE,
        )
    )


def signals(db: Session, now: datetime = NOW) -> dict[str, Any]:
    return {item.code: item for item in attention(db, now).signals}


def test_latest_job_failure_recovery_and_stale_running_are_distinct(
    customer_engine: Engine,
) -> None:
    with Session(customer_engine) as db:
        wid = workspace(db, "jobs").id
        job(db, wid, "recovered", JobRunStatus.FAILED, OLD)
        job(db, wid, "recovered", JobRunStatus.SUCCEEDED, NOW)
        job(db, wid, "failed", JobRunStatus.FAILED, OLD)
        job(db, wid, "slow", JobRunStatus.RUNNING, OLD)
        job(db, wid, "recent", JobRunStatus.RUNNING, NOW)
        db.commit()
        report = attention(db, NOW)
        assert report.status == "attention_observed"
        assert {s.code: s.observed_count for s in report.signals} == {
            "job_failed": 1,
            "job_running_overdue": 1,
        }
        assert PRIVATE not in report.model_dump_json()
        job(db, wid, "failed", JobRunStatus.SUCCEEDED, NOW)
        job(db, wid, "slow", JobRunStatus.SUCCEEDED, NOW)
        db.commit()
        assert attention(db, NOW).status == "no_attention_observed"
        assert "storage_failures_not_recorded" in attention(db, NOW).observation_gaps


def test_billing_backoff_is_expected_until_explicit_overdue_threshold(
    customer_engine: Engine,
) -> None:
    with Session(customer_engine) as db:
        wid = workspace(db, "billing").id
        db.add(
            WorkspaceBilling(
                workspace_id=wid,
                customer_request_key="key",
                customer_id="cus_fixture",
                subscription_id="sub_fixture",
                verified_at=OLD,
                next_attempt_at=NOW + timedelta(hours=1),
            )
        )
        db.add(
            BillingEvent(
                id="evt_fixture",
                body_hash="a" * 64,
                customer_id="cus_fixture",
                subscription_id="sub_fixture",
                event_type="customer.subscription.updated",
                received_at=OLD,
                error_code=PRIVATE,
                next_attempt_at=NOW + timedelta(hours=1),
            )
        )
        db.commit()
        assert not signals(db)
        assert not signals(db, NOW + timedelta(hours=1, seconds=OVERDUE_SECONDS - 1))
        actual = signals(db, NOW + timedelta(hours=1, seconds=OVERDUE_SECONDS))
        assert set(actual) == {"billing_event_overdue", "billing_snapshot_overdue"}
        row = db.get(BillingEvent, "evt_fixture")
        assert row
        row.state = "processed"
        billing = db.get(WorkspaceBilling, wid)
        assert billing
        billing.verified_at = NOW + timedelta(hours=2)
        db.commit()
        assert not signals(db, NOW + timedelta(hours=2))


def test_connection_terminal_uncertainty_and_retry_due_are_sanitized(
    customer_engine: Engine,
) -> None:
    with Session(customer_engine) as db:
        wid = workspace(db, "sources").id
        integration = WorkspaceIntegration(
            workspace_id=wid, integration_key="fixture", provider="omnisend", display_name=PRIVATE
        )
        db.add(integration)
        db.flush()
        for index, (state, error, due) in enumerate(
            [
                ("provider_error", "renewal_uncertain", None),
                ("reconnect_required", PRIVATE, None),
                ("connected", PRIVATE, NOW + timedelta(hours=1)),
                ("connected", PRIVATE, OLD),
            ]
        ):
            db.add(
                SourceConnection(
                    id=str(index),
                    workspace_id=wid,
                    integration_id=integration.id,
                    provider="omnisend",
                    external_id=str(index),
                    status=state,
                    error_code=error,
                    next_attempt_at=due,
                    encrypted_grant=PRIVATE,
                    window_start=NOW.date(),
                    window_end=NOW.date(),
                )
            )
        db.commit()
        report = attention(db, NOW)
        assert {s.code: s.observed_count for s in report.signals} == {
            "renewal_outcome_unknown": 1,
            "connection_reconnect_required": 1,
            "connection_retry_overdue": 1,
        }
        assert PRIVATE not in report.model_dump_json()
        assert (
            signals(db)["renewal_outcome_unknown"].action
            == "preserve_reservation_reconcile_no_retry"
        )


def test_unknown_publication_and_action_reservations_survive_workspace_closure(
    customer_engine: Engine,
) -> None:
    with Session(customer_engine) as db:
        wid = workspace(db, "closing", "closing").id
        mandate = Mandate(
            id="mandate",
            workspace_id=wid,
            revision=1,
            starts_at=OLD,
            ends_at=NOW,
            reserved_micros=123,
            state="approved",
        )
        db.add(mandate)
        db.flush()
        db.add(
            MandateAction(
                id="action",
                mandate_id=mandate.id,
                workspace_id=wid,
                draft={"private": PRIVATE},
                digest="a" * 64,
                state="outcome_unknown",
                dispatch_at=OLD,
            )
        )
        db.flush()
        db.add(
            PublicationPlanRecord(
                id="plan",
                workspace_id=wid,
                action_id="action",
                digest="b" * 64,
                document={"private": PRIVATE},
            )
        )
        db.flush()
        db.add(
            PublicationStepRecord(
                plan_id="plan",
                step_id="step",
                workspace_id=wid,
                state="unknown",
                request={"private": PRIVATE},
            )
        )
        db.commit()
        report = attention(db, NOW)
        assert set(s.code for s in report.signals) == {
            "publication_outcome_unknown",
            "action_outcome_unknown",
        }
        assert all(s.severity == "critical" for s in report.signals)
        assert PRIVATE not in report.model_dump_json()
        saved_mandate = db.get(Mandate, "mandate")
        saved_step = db.get(PublicationStepRecord, ("plan", "step"))
        assert saved_mandate and saved_mandate.reserved_micros == 123
        assert saved_step and saved_step.state == "unknown"
        saved_action = db.get(MandateAction, "action")
        assert saved_action
        saved_action.state, saved_action.dispatch_at = "dispatching", NOW
        db.commit()
        assert set(signals(db)) == {"publication_outcome_unknown"}
        saved_action.dispatch_at = OLD
        db.commit()
        assert set(signals(db)) == {"publication_outcome_unknown", "action_dispatch_overdue"}


def test_capped_evidence_never_claims_complete_health(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        wid = workspace(db, "bounded").id
        for index in range(ROW_LIMIT + 1):
            job(db, wid, str(index), JobRunStatus.FAILED, OLD)
        db.commit()
        statements = []

        def record(
            _conn: Any, _cursor: Any, sql: str, _params: Any, _context: Any, _many: bool
        ) -> None:
            statements.append(sql)

        event.listen(customer_engine, "before_cursor_execute", record)
        try:
            result = attention(db, NOW)
        finally:
            event.remove(customer_engine, "before_cursor_execute", record)
        assert result.evidence_truncated and result.counts_are_lower_bounds
        assert result.signals[0].observed_count == ROW_LIMIT
        assert len(statements) == (10 if customer_engine.dialect.name == "postgresql" else 9)
        assert all("LIMIT" in statement or "set_config" in statement for statement in statements)
        if customer_engine.dialect.name == "postgresql":
            assert db.scalar(select(func.current_setting("statement_timeout"))) == "2s"


def test_operator_route_is_no_store_and_publishes_no_sensitive_evidence(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "api_token", SecretStr("o" * 43))

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    monkeypatch.setattr(app, "dependency_overrides", {get_db: database})
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/operations/attention", headers={"Authorization": "Bearer " + "o" * 43}
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["schema_version"] == "inlet.operations.attention.v1"
        assert response.json()["status"] == "no_attention_observed"
        assert response.json()["observation_gaps"]


def test_query_failure_remains_unavailable_and_sanitized(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "api_token", SecretStr("o" * 43))

    def unavailable() -> None:
        raise OperationalError(PRIVATE, {"private": PRIVATE}, RuntimeError(PRIVATE))

    monkeypatch.setattr(app, "dependency_overrides", {get_db: unavailable})
    with TestClient(app) as client:
        result = client.get(
            "/api/v1/operations/attention", headers={"Authorization": "Bearer " + "o" * 43}
        )
    assert result.status_code == 503
    assert result.json() == {"detail": "database temporarily unavailable"}
    assert PRIVATE not in result.text and PRIVATE not in caplog.text
