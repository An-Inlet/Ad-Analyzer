from sqlalchemy.orm import Session

from app.ads.models import DailyMetric
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import NormalizedMetricsBatch


class NormalizedMetricsService:
    """Stores normalized advertising metrics without contacting ad platforms."""

    def __init__(self, session: Session) -> None:
        self.repository = AdvertisingMetricsRepository(session)

    def store_batch(self, batch: NormalizedMetricsBatch) -> list[DailyMetric]:
        return self.repository.add_daily_metrics(batch.metrics)
