from app.ads.services import GoogleAdsSyncService
from app.database.session import SessionLocal


def main() -> None:
    with SessionLocal() as session:
        result = GoogleAdsSyncService(session).sync()
    print(
        "Google Ads read-only sync completed: "
        f"job_run_id={result.job_run_id} records_processed={result.records_processed}"
    )


if __name__ == "__main__":
    main()
