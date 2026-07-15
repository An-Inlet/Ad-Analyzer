import sys

from app.ads.services import GoogleAdsSyncError, GoogleAdsSyncService
from app.database.session import SessionLocal


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
