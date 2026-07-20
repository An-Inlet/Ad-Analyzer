from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MIN_COVERAGE_RATIO = Decimal("0.50")


@dataclass(frozen=True)
class MetricWindow:
    date_from: date
    date_to: date
    window_days: int
    days_with_metric_rows: int
    impressions: int
    clicks: int
    cost_micros: int
    conversions: Decimal
    conversion_value_micros: int

    @property
    def days_with_metrics(self) -> int:
        """Backward-compatible alias for templates/tests that still use the old name."""
        return self.days_with_metric_rows

    @property
    def data_coverage_ratio(self) -> Decimal:
        if self.window_days <= 0:
            return Decimal("0")
        return Decimal(self.days_with_metric_rows) / Decimal(self.window_days)

    @property
    def has_metric_rows(self) -> bool:
        return self.days_with_metric_rows > 0

    @property
    def has_minimum_coverage(self) -> bool:
        return self.has_metric_rows and self.data_coverage_ratio >= MIN_COVERAGE_RATIO

    @property
    def coverage_status(self) -> str:
        if not self.has_metric_rows:
            return "unavailable"
        if self.has_minimum_coverage:
            return "sufficient"
        return "partial"

    @property
    def ctr(self) -> Decimal:
        return (
            Decimal(self.clicks) / Decimal(self.impressions) if self.impressions else Decimal("0")
        )

    @property
    def average_cpc_micros(self) -> Decimal:
        return Decimal(self.cost_micros) / Decimal(self.clicks) if self.clicks else Decimal("0")

    @property
    def conversion_rate(self) -> Decimal:
        return self.conversions / Decimal(self.clicks) if self.clicks else Decimal("0")

    @property
    def cost_per_conversion_micros(self) -> Decimal:
        return Decimal(self.cost_micros) / self.conversions if self.conversions else Decimal("0")

    @property
    def roas(self) -> Decimal:
        return (
            Decimal(self.conversion_value_micros) / Decimal(self.cost_micros)
            if self.cost_micros
            else Decimal("0")
        )


def inclusive_window_days(date_from: date, date_to: date) -> int:
    return (date_to - date_from).days + 1


def percent_delta(current: Decimal, comparison: Decimal) -> Decimal | None:
    if comparison == 0:
        return None
    return (current - comparison) / comparison
