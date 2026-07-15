import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.ads.services import GoogleAdsSyncError, GoogleAdsSyncService  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402


def main() -> int:
    try:
        with SessionLocal() as session:
            result = GoogleAdsSyncService(session).sync()
    except GoogleAdsSyncError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "Google Ads read-only sync completed: "
        f"job_run_id={result.job_run_id} records_processed={result.records_processed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
