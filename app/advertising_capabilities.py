"""The planning MVP artifact has no advertising mutation capability.

This is a code-level product boundary, not a customer permission or environment
switch. Billing, connection maintenance and application persistence are unrelated.
Retained execution engines may be exercised by explicit offline test patches only;
no runtime flag, manifest, approval or injected provider grants this capability.
"""

from fastapi import HTTPException


class AdvertisingWritesDisabled(HTTPException):
    """Deterministic pre-emission denial, never an uncertain provider outcome."""

    def __init__(self) -> None:
        super().__init__(status_code=409, detail="advertising_writes_disabled_in_planning_mvp")


def advertising_writes_enabled() -> bool:
    return False


def require_advertising_write() -> None:
    """Always deny. Annotate None so retained engine bodies remain type-checked."""
    raise AdvertisingWritesDisabled()
