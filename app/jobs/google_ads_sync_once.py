"""One-shot Google Ads synchronization worker entrypoint."""

import logging
import sys

from app.ads.enums import JobRunStatus
from app.database.session import engine
from app.jobs.reliability import run_cycle
from app.settings import settings

SUCCESS_EXIT_CODE = 0
FAILURE_EXIT_CODE = 1
OVERLAP_EXIT_CODE = 2


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        outcome = run_cycle(settings, engine)
        if outcome.skipped:
            logging.getLogger(__name__).info("google_ads_sync_worker_skipped_overlap")
            return OVERLAP_EXIT_CODE
        if outcome.result is not None and outcome.result.status is JobRunStatus.SUCCEEDED:
            return SUCCESS_EXIT_CODE
        return FAILURE_EXIT_CODE
    except Exception as exc:
        logging.getLogger(__name__).error(
            "google_ads_sync_worker_failed error_type=%s", type(exc).__name__
        )
        return FAILURE_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
