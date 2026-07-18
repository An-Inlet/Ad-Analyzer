"""One-shot Google Ads synchronization worker entrypoint."""

import logging
import sys
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


def main(runtime_loader: Any = _load_runtime) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        settings, engine, run_cycle, job_run_status = runtime_loader()
        outcome = run_cycle(settings, engine)
        if outcome.skipped:
            logger.info("google_ads_sync_worker_skipped_overlap")
            return OVERLAP_EXIT_CODE
        if outcome.result is not None and outcome.result.status is job_run_status.SUCCEEDED:
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


if __name__ == "__main__":
    sys.exit(main())
