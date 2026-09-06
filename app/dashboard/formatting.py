"""Presentation-only Decimal-safe formatting functions."""

from decimal import ROUND_HALF_UP, Decimal


def money_from_micros(value: int | Decimal | None, currency: str = "USD") -> str:
    if value is None:
        return "Not available"
    amount = Decimal(value) / Decimal("1000000")
    return f"{currency} {amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,}"


def ratio_percent(value: Decimal | int | float | None) -> str:
    if value is None:
        return "Not available"
    number = Decimal(str(value))
    if not number.is_finite():
        return "Not available"
    return f"{(number * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"
