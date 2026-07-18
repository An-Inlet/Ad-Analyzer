"""Standalone recurring Google Ads sync scheduler; never import from FastAPI."""

import logging
import signal
import time
from threading import Event
from typing import Any

logger = logging.getLogger(__name__)


def _load_runtime() -> tuple[Any, Any, Any]:
    """Load settings, database, and worker code inside sanitized startup handling."""
    from app.database.session import engine
    from app.jobs.reliability import run_cycle
    from app.settings import settings

    return settings, engine, run_cycle


def main(stop_event: Event | None = None, runtime_loader: Any = _load_runtime) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        settings, engine, run_cycle = runtime_loader()
    except Exception as exc:
        logger.error("google_ads_scheduler_startup_failed error_type=%s", type(exc).__name__)
        return 1
    stop = stop_event or Event()
    if stop_event is None:
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
    interval_seconds = settings.sync_interval_minutes * 60
    immediate = settings.sync_run_immediately
    initial_now = time.monotonic()
    deadline = initial_now if immediate else initial_now + interval_seconds
    while not stop.is_set():
        now = time.monotonic()
        if immediate or now >= deadline:
            immediate = False
            try:
                run_cycle(settings, engine, wait=stop.wait, stop_requested=stop.is_set)
            except KeyboardInterrupt:
                logger.error("google_ads_scheduler_cycle_interrupted")
                stop.set()
                break
            except Exception as exc:
                logger.error("google_ads_scheduler_cycle_failed error_type=%s", type(exc).__name__)
            deadline = time.monotonic() + interval_seconds
            now = time.monotonic()
        stop.wait(max(0.0, deadline - now))
    logger.info("google_ads_scheduler_stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
