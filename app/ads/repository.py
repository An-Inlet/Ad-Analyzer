from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.ads.models import DailyMetric
from app.ads.schemas import DailyMetricCreate


class AdvertisingMetricsRepository:
    """Repository for local, normalized, read-only advertising metric storage."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_daily_metric(self, metric: DailyMetricCreate) -> DailyMetric:
        db_metric = DailyMetric(**metric.model_dump())
        self.session.add(db_metric)
        return db_metric

    def add_daily_metrics(self, metrics: Sequence[DailyMetricCreate]) -> list[DailyMetric]:
        return [self.add_daily_metric(metric) for metric in metrics]
