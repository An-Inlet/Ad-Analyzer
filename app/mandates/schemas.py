import hashlib
import json
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel


class AccountScope(StrictModel):
    account_id: int = Field(strict=True, gt=0)
    connection_id: int = Field(strict=True, gt=0)
    platform: Literal["google_ads", "meta_ads", "tiktok_ads"]


class MandateDefinition(StrictModel):
    mode: Literal["simulation"] = "simulation"
    goal_id: str = Field(min_length=32, max_length=32)
    goal_revision: int = Field(strict=True, ge=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    accounts: list[AccountScope] = Field(min_length=1, max_length=20)
    total_cap_micros: int = Field(strict=True, ge=0, le=10**15)
    per_action_cap_micros: int = Field(strict=True, ge=0, le=10**15)
    positive_change_cap_micros: int = Field(strict=True, ge=0, le=10**15)
    action_limit: int = Field(strict=True, ge=0, le=1000)
    cooldown_seconds: int = Field(strict=True, ge=0, le=86400)
    freshness_seconds: int = Field(strict=True, ge=1, le=3600)
    allowed_actions: list[
        Literal["budget_change", "pause", "resume", "new_campaign", "creative"]
    ] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def valid(self) -> "MandateDefinition":
        try:
            ZoneInfo(self.time_zone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("invalid time zone") from None
        if not 0 < (self.ends_at - self.starts_at).total_seconds() <= 366 * 86400:
            raise ValueError("invalid fixed period")
        if self.per_action_cap_micros > self.total_cap_micros:
            raise ValueError("action cap exceeds mandate")
        if len({a.account_id for a in self.accounts}) != len(self.accounts):
            raise ValueError("duplicate account scope")
        return self


class MandateEdit(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    definition: MandateDefinition


class RevisionInput(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)


class ActionDraft(StrictModel):
    account: AccountScope
    kind: Literal["budget_change", "pause", "resume", "new_campaign", "creative"]
    resource_key: str = Field(min_length=1, max_length=128)
    # Reviewable synthetic draft; no fetching assets or accepting executable code.
    payload: dict[str, str | int | bool] = Field(min_length=1, max_length=30)
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_state_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    exposure_micros: int = Field(strict=True, ge=0, le=10**15)
    positive_change_micros: int = Field(strict=True, ge=0, le=10**15)
    mandate_revision: int = Field(strict=True, ge=1)

    @model_validator(mode="after")
    def payload_matches(self) -> "ActionDraft":
        content = json.dumps(self.payload, sort_keys=True, separators=(",", ":")).encode()
        if len(content) > 8192 or hashlib.sha256(content).hexdigest() != self.payload_digest:
            raise ValueError("draft payload digest mismatch")
        return self


class ReviewInput(StrictModel):
    draft_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class SyntheticEvidence(StrictModel):
    mode: Literal["simulation"] = "simulation"
    state_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_at: AwareDatetime
    bound_micros: int = Field(strict=True, ge=0, le=10**15)
    entitlement_active: bool
    period_consumed_micros: int = Field(strict=True, ge=0, le=10**15)
    covered_account_ids: list[int] = Field(min_length=1, max_length=20)


class ClaimInput(StrictModel):
    request_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    evidence: SyntheticEvidence


class DispatchInput(StrictModel):
    fence: str = Field(min_length=32, max_length=32)
    evidence: SyntheticEvidence


class ReconcileInput(StrictModel):
    fence: str = Field(min_length=32, max_length=32)
    outcome: Literal["success", "no_effect", "unknown"]
    consumed_micros: int = Field(default=0, strict=True, ge=0, le=10**15)
    evidence_at: AwareDatetime
    period_consumed_micros: int = Field(strict=True, ge=0, le=10**15)
