"""Presentation-only Decimal-safe formatting functions."""

from decimal import ROUND_HALF_UP, Decimal


def money_from_micros(value: int | Decimal, currency: str = "USD") -> str:
    amount = Decimal(value) / Decimal("1000000")
    return f"{currency} {amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,}"


def ratio_percent(value: Decimal) -> str:
    return f"{(value * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"
