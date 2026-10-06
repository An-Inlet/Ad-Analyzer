"""Standalone recurring Google Ads sync scheduler; never import from FastAPI."""

from __future__ import annotations

import logging
import signal
import time
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from app.operations.observation_contracts import ObservationSink, Outcome, Slot


def _observation_sink() -> ObservationSink | None:
    # Preserve sanitized startup: settings/model imports happen after runtime loading.
    from app.operations.observations import get_observation_sink

    return get_observation_sink()


logger = logging.getLogger(__name__)


FAILURE_EXIT_CODE = 1
SUCCESS_EXIT_CODE = 0


def _load_runtime() -> tuple[Any, Any, Any]:
    """Load settings, database, and worker code inside sanitized startup handling."""
    from app.database.models import register_models
    from app.database.session import engine
    from app.jobs.reliability import run_cycle
    from app.settings import settings

    register_models()
    return settings, engine, run_cycle


def _run_analysis_tick(engine: Any, outcome: Any | None) -> bool:
    """Load Step 4 only for a real SQLAlchemy runtime, not lightweight unit-test doubles."""
    from sqlalchemy import Engine

    if not isinstance(engine, Engine):
        return True
    from app.analysis.cadence import run_analysis_tick
    from app.jobs.customer_runtime import run_customer_tick
    from app.meta.sync import run_meta_tick
    from app.shopify.privacy import purge_expired_facts, run_privacy_tick
    from app.shopify.sync import run_shopify_tick

    successful = True
    for operation in (
        purge_expired_facts,
        run_privacy_tick,
        run_shopify_tick,
        run_meta_tick,
        run_customer_tick,
    ):
        try:
            result = operation(engine)
            if isinstance(result, dict) and "failed" in result.values():
                successful = False
        except Exception:
            successful = False
            logger.warning("independent_source_operation_failed")
    run_analysis_tick(engine, outcome)
    return successful


def _install_signal_handlers(stop: Event) -> dict[int, Any]:
    previous: dict[int, Any] = {}
    for signum_name in ("SIGINT", "SIGTERM"):
        signum = getattr(signal, signum_name, None)
        if signum is None:
            continue
        try:
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, lambda *_args: stop.set())
        except (ValueError, OSError, RuntimeError):
            previous.pop(signum, None)
    return previous


def _restore_signal_handlers(previous: dict[int, Any]) -> None:
    for signum, handler in previous.items():
        try:
            signal.signal(signum, handler)
        except (ValueError, OSError, RuntimeError):
            continue


def main(
    stop_event: Event | None = None,
    runtime_loader: Any = _load_runtime,
    analysis_tick: Any = _run_analysis_tick,
    observation_factory: Any = _observation_sink,
) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stop = stop_event or Event()
    previous_handlers: dict[int, Any] = {}
    if stop_event is None:
        previous_handlers = _install_signal_handlers(stop)
    try:
        if stop.is_set():
            logger.error("google_ads_scheduler_startup_interrupted")
            return FAILURE_EXIT_CODE
        try:
            settings, engine, run_cycle = runtime_loader()
        except Exception as exc:
            event = (
                "google_ads_scheduler_startup_interrupted"
                if stop.is_set()
                else "google_ads_scheduler_startup_failed"
            )
            logger.error("%s error_type=%s", event, type(exc).__name__)
            return FAILURE_EXIT_CODE
        if stop.is_set():
            logger.error("google_ads_scheduler_startup_interrupted")
            return FAILURE_EXIT_CODE
        from app.operations.observation_contracts import OperationalObservation
        from app.operations.observations import record_safely

        sink: ObservationSink | None = None
        try:
            sink = observation_factory()
        except Exception:
            logger.warning("operational_observation_unavailable")
        epoch, epoch_start = uuid4().hex, datetime.now(UTC)
        interval_seconds = settings.sync_interval_minutes * 60

        def observe(slot: Slot, outcome: Outcome, *, next_cycle: bool = False) -> None:
            observed = max(epoch_start, datetime.now(UTC))
            record_safely(
                sink,
                OperationalObservation(
                    component="scheduler_loop",
                    slot=slot,
                    outcome=outcome,
                    observed_at=observed,
                    process_epoch=epoch,
                    epoch_started_at=epoch_start,
                    expected_next_at=(observed + timedelta(seconds=interval_seconds))
                    if next_cycle
                    else None,
                ),
            )

        immediate = settings.sync_run_immediately
        initial_now = time.monotonic()
        deadline = initial_now if immediate else initial_now + interval_seconds
        while not stop.is_set():
            now = time.monotonic()
            if immediate or now >= deadline:
                if stop.is_set():
                    break
                immediate = False
                cycle_outcome: Any | None = None
                successful = True
                observe("latest_start", "scheduler_cycle_started")
                try:
                    cycle_outcome = run_cycle(
                        settings,
                        engine,
                        wait=stop.wait,
                        stop_requested=stop.is_set,
                    )
                except KeyboardInterrupt:
                    observe("latest_failure", "scheduler_interrupted")
                    logger.error("google_ads_scheduler_cycle_interrupted")
                    stop.set()
                    break
                except Exception as exc:
                    successful = False
                    observe("latest_failure", "scheduler_cycle_failed")
                    logger.error(
                        "google_ads_scheduler_cycle_failed error_type=%s", type(exc).__name__
                    )
                if not stop.is_set():
                    try:
                        if analysis_tick(engine, cycle_outcome) is False:
                            successful = False
                            observe("latest_failure", "scheduler_stage_failed")
                    except KeyboardInterrupt:
                        observe("latest_failure", "scheduler_interrupted")
                        logger.error("analysis_scheduler_tick_interrupted")
                        stop.set()
                        break
                    except Exception as exc:
                        successful = False
                        observe("latest_failure", "scheduler_stage_failed")
                        logger.error(
                            "analysis_scheduler_tick_failed error_type=%s",
                            type(exc).__name__,
                        )
                if successful and not stop.is_set():
                    observe("latest_completion", "scheduler_cycle_completed", next_cycle=True)
                elif successful:
                    observe("latest_failure", "scheduler_interrupted")
                deadline = time.monotonic() + interval_seconds
                now = time.monotonic()
            stop.wait(max(0.0, deadline - now))
        logger.info("google_ads_scheduler_stopped")
        return SUCCESS_EXIT_CODE
    finally:
        _restore_signal_handlers(previous_handlers)


if __name__ == "__main__":
    raise SystemExit(main())
