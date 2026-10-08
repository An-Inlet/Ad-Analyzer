"""Unpatched planning policy denies stale/direct execution before durable effects."""

import importlib
import inspect
from collections.abc import Iterator

import pytest
from app.advertising_capabilities import AdvertisingWritesDisabled
from app.jobs import customer_runtime
from app.production_runtime import reported_automation
from app.session_automation import worker
from app.settings import Settings
from sqlalchemy import Engine, create_engine, event

pytestmark = pytest.mark.planning_boundary

ENTRYPOINTS = {
    "app.publication.coordinator": (
        "prepare_creation",
        "approve_creation",
        "create_run",
        "claim_creation_step",
        "execute_claim",
    ),
    "app.publication.activation": ("claim_step", "execute_claim"),
    "app.publication.activation_review": ("prepare_activation", "approve_activation", "create_run"),
    "app.publication.optimization": (
        "prepare_optimization",
        "approve_optimization",
        "create_run",
        "claim_step",
        "execute_claim",
    ),
    "app.publication.service": (
        "prepare",
        "approve",
        "claim_next",
        "dispatch_next",
        "approve_activation",
    ),
    "app.publication.replacement": ("prepare_repeat_optimization", "transfer"),
    "app.publication.provider_service": ("prepare_google", "approve"),
    "app.publication.execution_mandates": ("consent",),
    "app.initial_planning.start_service": ("start_initial",),
    "app.mandates.service": ("approve", "review", "claim", "dispatch"),
    "app.session_automation.service": ("start",),
    "app.session_automation.admission": ("admit",),
    "app.session_automation.worker": ("advance",),
}


class Untouchable:
    def __getattr__(self, name: str) -> object:
        raise AssertionError("denial must precede database, authority or provider access")


@pytest.mark.parametrize(
    ("module", "name"), [(m, n) for m, names in ENTRYPOINTS.items() for n in names]
)
def test_direct_execution_denied_before_resolving_any_input(module: str, name: str) -> None:
    operation = getattr(importlib.import_module(module), name)
    arguments = {p: Untouchable() for p in inspect.signature(operation).parameters}
    with pytest.raises(AdvertisingWritesDisabled) as denied:
        operation(**arguments)
    assert denied.value.status_code == 409


@pytest.fixture
def untouched_engine() -> Iterator[Engine]:
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "before_cursor_execute")
    def no_statement(*args: object) -> None:
        raise AssertionError("disabled automation must not read or mutate queued work")

    yield engine
    engine.dispose()


def forbidden_factory() -> None:
    raise AssertionError("disabled automation must not construct credentials or transports")


def test_stale_automation_settings_do_not_admit_jobs(untouched_engine: Engine) -> None:
    settings = Settings(INLET_CUSTOMER_SESSION_AUTOMATION_ENABLED=True)
    assert settings.customer_session_automation_enabled is True
    assert worker.run_due(untouched_engine, forbidden_factory) == {}
    assert reported_automation.run_configured_session_automation(untouched_engine, settings) == {}
    with reported_automation.configured_session_automation(
        Untouchable(),  # type: ignore[arg-type]
        Untouchable(),  # type: ignore[arg-type]
        Untouchable(),  # type: ignore[arg-type]
        settings,
    ) as runtime:
        assert runtime is None


def test_tick_retains_read_stages_without_calling_automation(
    monkeypatch: pytest.MonkeyPatch, untouched_engine: Engine
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(customer_runtime, "master_control_enabled", lambda *_: True)
    monkeypatch.setattr(customer_runtime, "run_imports", lambda *_: calls.append("google_read"))
    monkeypatch.setattr(customer_runtime, "run_tiktok", lambda *_: calls.append("tiktok_read"))
    monkeypatch.setattr(
        customer_runtime, "deliver_analysis", lambda *a, **k: calls.append("analysis")
    )
    settings = Settings(
        INLET_CUSTOMER_SESSION_AUTOMATION_ENABLED=True,
        AD_ANALYZER_CUSTOMER_GOOGLE_SCHEDULER_ENABLED=True,
        AD_ANALYZER_CUSTOMER_TIKTOK_SCHEDULER_ENABLED=True,
        AD_ANALYZER_CUSTOMER_ANALYSIS_OUTBOX_ENABLED=True,
        customer_candidate_reads_enabled=False,
        AD_ANALYZER_CUSTOMER_BILLING_SCHEDULER_ENABLED=False,
    )
    result = customer_runtime.run_customer_tick(
        untouched_engine,
        configuration=settings,
        google_factory=lambda: object(),  # type: ignore[arg-type,return-value]
        tiktok_factory=lambda: object(),  # type: ignore[arg-type,return-value]
        automation_factory=forbidden_factory,
    )
    assert calls == ["google_read", "tiktok_read", "analysis"]
    assert result == {
        "google": "completed",
        "tiktok": "completed",
        "analysis_outbox": "completed",
        "session_automation": "disabled_planning_mvp",
    }
