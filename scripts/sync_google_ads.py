import sys
from collections.abc import Callable
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def main(worker_main: Callable[[], int] | None = None) -> int:
    resolved_worker = worker_main
    if resolved_worker is None:
        from app.jobs.google_ads_sync_once import main as one_shot_main

        resolved_worker = one_shot_main

    return resolved_worker()


if __name__ == "__main__":
    raise SystemExit(main())
