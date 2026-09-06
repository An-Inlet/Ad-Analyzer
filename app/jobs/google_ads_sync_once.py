"""One-shot Google Ads synchronization worker entrypoint."""

import logging
import signal
import sys
from threading import Event
from typing import Any

SUCCESS_EXIT_CODE = 0
FAILURE_EXIT_CODE = 1
OVERLAP_EXIT_CODE = 2

logger = logging.getLogger(__name__)


def _load_runtime() -> tuple[Any, Any, Any, Any]:
    """Load settings, database, and worker code inside sanitized startup handling."""
    from app.ads.enums import JobRunStatus
    from app.database.session import engine
    from app.jobs.reliability import run_cycle
    from app.settings import settings

    return settings, engine, run_cycle, JobRunStatus


def _run_post_sync_analysis(engine: Any, source_job_run_id: int) -> None:
    """Load Step 4 only for a real SQLAlchemy runtime, not lightweight unit-test doubles."""
    from sqlalchemy import Engine

    if not isinstance(engine, Engine):
        return
    from app.analysis.cadence import run_post_sync_analysis

    run_post_sync_analysis(engine, source_job_run_id)


def _install_signal_handlers(stop: Event) -> dict[int, Any]:
    previous: dict[int, Any] = {}
    for signum_name in ("SIGINT", "SIGTERM"):
        signum = getattr(signal, signum_name, None)
        if signum is None:
            continue
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, lambda *_: stop.set())
    return previous


def _restore_signal_handlers(previous: dict[int, Any]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def main(
    runtime_loader: Any = _load_runtime,
    post_sync_analysis: Any = _run_post_sync_analysis,
) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    previous_handlers: dict[int, Any] = {}
    stop = Event()
    previous_handlers = _install_signal_handlers(stop)
    try:
        settings, engine, run_cycle, job_run_status = runtime_loader()
        if stop.is_set():
            logger.error("google_ads_sync_worker_interrupted")
            return FAILURE_EXIT_CODE
        outcome = run_cycle(settings, engine, wait=stop.wait, stop_requested=stop.is_set)
        # Run independent Shopify maintenance and due analyses even when Ads is disabled.
        try:
            from app.jobs.google_ads_scheduler import _run_analysis_tick

            _run_analysis_tick(engine, None)
        except Exception as exc:
            logger.error("independent_analysis_tick_failed error_type=%s", type(exc).__name__)
        if outcome.skipped:
            if getattr(outcome, "skip_reason", None) == "disabled":
                logger.info("google_ads_sync_worker_skipped_disabled")
                return SUCCESS_EXIT_CODE
            logger.info("google_ads_sync_worker_skipped_overlap")
            return OVERLAP_EXIT_CODE
        if outcome.result is not None and outcome.result.status is job_run_status.SUCCEEDED:
            try:
                post_sync_analysis(engine, outcome.result.job_run_id)
            except Exception as exc:
                logger.error("post_sync_analysis_failed error_type=%s", type(exc).__name__)
            return SUCCESS_EXIT_CODE
        return FAILURE_EXIT_CODE
    except KeyboardInterrupt:
        logger.error("google_ads_sync_worker_interrupted")
        return FAILURE_EXIT_CODE
    except SystemExit:
        raise
    except Exception as exc:
        logger.error("google_ads_sync_worker_failed error_type=%s", type(exc).__name__)
        return FAILURE_EXIT_CODE
    finally:
        _restore_signal_handlers(previous_handlers)


if __name__ == "__main__":
    sys.exit(main())
