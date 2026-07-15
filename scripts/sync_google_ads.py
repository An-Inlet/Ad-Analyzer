import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

STARTUP_ERROR_MESSAGE = (
    "Google Ads sync could not start because local configuration or database "
    "initialization failed"
)


def _load_runtime() -> tuple[type[BaseException], type[Any], Callable[[], Any]]:
    from app.ads.services import GoogleAdsSyncError, GoogleAdsSyncService
    from app.database.session import SessionLocal

    return GoogleAdsSyncError, GoogleAdsSyncService, SessionLocal


def main() -> int:
    try:
        sync_error_type, sync_service_type, session_factory = _load_runtime()
    except Exception:
        print(STARTUP_ERROR_MESSAGE, file=sys.stderr)
        return 1
    try:
        with session_factory() as session:
            result = sync_service_type(session).sync()
    except Exception as exc:
        if isinstance(exc, sync_error_type):
            print(str(exc), file=sys.stderr)
        else:
            print(STARTUP_ERROR_MESSAGE, file=sys.stderr)
        return 1
    print(
        "Google Ads read-only sync completed: "
        f"job_run_id={result.job_run_id} records_processed={result.records_processed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
