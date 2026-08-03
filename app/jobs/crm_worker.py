"""Run the private CRM Pub/Sub pull worker."""

import logging

from app.crm.worker import handle_message
from app.database.session import SessionLocal
from app.settings import settings
from google.cloud import pubsub_v1  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def main() -> None:
    if not settings.crm_pubsub_project_id or not settings.crm_pubsub_subscription_id:
        raise RuntimeError("CRM subscription is not configured")
    subscriber = pubsub_v1.SubscriberClient()
    path = subscriber.subscription_path(
        settings.crm_pubsub_project_id, settings.crm_pubsub_subscription_id
    )

    def callback(message: object) -> None:
        with SessionLocal() as session:
            handle_message(message, session)  # type: ignore[arg-type]

    future = subscriber.subscribe(path, callback=callback)
    logger.info("CRM worker started")
    try:
        future.result()
    finally:
        future.cancel()
        subscriber.close()


if __name__ == "__main__":
    main()
