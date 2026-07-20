from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MIN_COVERAGE_DAYS = 7


@dataclass(frozen=True)
class MetricWindow:
    date_from: date
    date_to: date
    days_with_metrics: int
    impressions: int
    clicks: int
    cost_micros: int
    conversions: Decimal
    conversion_value_micros: int

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

    @property
    def has_minimum_coverage(self) -> bool:
        return self.days_with_metrics >= MIN_COVERAGE_DAYS


def percent_delta(current: Decimal, comparison: Decimal) -> Decimal | None:
    if comparison == 0:
        return None
    return (current - comparison) / comparison
