"""Bounded document primitives, not recommendation thresholds or runtime permissions."""

import hashlib
import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Operational ceilings bound parsing, review and export size. They prescribe no
# allocation, forecast, freshness lifetime or aggressiveness policy.
MAX_ACCOUNTS = 20
MAX_EVIDENCE = 400
MAX_ACTIONS = 100
MAX_SCENARIOS = 8
MAX_BRIEFS = 30
MAX_DOCUMENT_BYTES = 1_048_576
Id = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{32}$")]
Digest = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{64}$")]
Key = Annotated[str, Field(strict=True, pattern=r"^[a-z][a-z0-9_:-]{0,95}$")]
Positive = Annotated[int, Field(strict=True, gt=0)]
Amount = Annotated[int, Field(strict=True, ge=0, le=10**15)]
SignedAmount = Annotated[int, Field(strict=True, ge=-(10**15), le=10**15)]
Currency = Annotated[str, Field(strict=True, pattern=r"^[A-Z]{3}$")]
Title = Annotated[str, Field(strict=True, min_length=1, max_length=160)]
Text = Annotated[str, Field(strict=True, min_length=1, max_length=2000)]
Platform = Literal["google_ads", "meta_ads", "tiktok_ads"]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")

    def digest(self) -> str:
        return fingerprint(
            type(self).__name__, type(self).model_validate(self).model_dump(mode="json")
        )


def fingerprint(domain: str, data: dict[str, Any]) -> str:
    payload = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()
    return hashlib.sha256(
        b"inlet.planning-documents.v1\0" + domain.encode() + b"\0" + payload
    ).hexdigest()


def unique(values: tuple[Any, ...] | list[Any], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label}")


class NoAuthority(Frozen):
    advertising_writes_enabled: Literal[False] = False
    spending_authority: Literal["none"] = "none"

    @field_validator("advertising_writes_enabled", mode="before")
    @classmethod
    def exact_false(cls, value: Any) -> Any:
        if value is not False:
            raise ValueError("advertising writes must be exactly false")
        return value
