"""Initial bounded native budget currency coverage; never a fallback exponent."""


def supported_budget_exponent(currency: str) -> int:
    # This initial read assembly supports USD only. Other currencies remain an
    # implementation backlog item; existing qualified adapters are unaffected.
    if currency != "USD":
        raise ValueError("native budget currency unsupported")
    return 2
