"""Standalone recurring Google Ads sync scheduler; never import from FastAPI."""

import logging
import signal
import time
from threading import Event
from typing import Any

logger = logging.getLogger(__name__)


FAILURE_EXIT_CODE = 1
SUCCESS_EXIT_CODE = 0


def _load_runtime() -> tuple[Any, Any, Any]:
    """Load settings, database, and worker code inside sanitized startup handling."""
    from app.database.session import engine
    from app.jobs.reliability import run_cycle
    from app.settings import settings

    return settings, engine, run_cycle


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


def main(stop_event: Event | None = None, runtime_loader: Any = _load_runtime) -> int:
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
        interval_seconds = settings.sync_interval_minutes * 60
        immediate = settings.sync_run_immediately
        initial_now = time.monotonic()
        deadline = initial_now if immediate else initial_now + interval_seconds
        while not stop.is_set():
            now = time.monotonic()
            if immediate or now >= deadline:
                if stop.is_set():
                    break
                immediate = False
                try:
                    run_cycle(settings, engine, wait=stop.wait, stop_requested=stop.is_set)
                except KeyboardInterrupt:
                    logger.error("google_ads_scheduler_cycle_interrupted")
                    stop.set()
                    break
                except Exception as exc:
                    logger.error(
                        "google_ads_scheduler_cycle_failed error_type=%s", type(exc).__name__
                    )
                deadline = time.monotonic() + interval_seconds
                now = time.monotonic()
            stop.wait(max(0.0, deadline - now))
        logger.info("google_ads_scheduler_stopped")
        return SUCCESS_EXIT_CODE
    finally:
        _restore_signal_handlers(previous_handlers)


if __name__ == "__main__":
    raise SystemExit(main())
