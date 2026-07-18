"""One-shot Google Ads synchronization worker entrypoint."""

import logging
import sys

from app.database.session import SessionLocal
from app.jobs.reliability import run_cycle
from app.settings import settings


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        run_cycle(settings, SessionLocal)
        return 0
    except Exception as exc:
        logging.getLogger(__name__).error(
            "google_ads_sync_worker_failed error_type=%s", type(exc).__name__
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
