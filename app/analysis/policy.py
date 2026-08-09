from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class AnalysisCadencePolicyError(RuntimeError):
    """Sanitized failure for invalid workspace cadence configuration."""

    def __init__(self) -> None:
        super().__init__("Invalid workspace analysis cadence configuration.")


class PostSyncCadence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    window_days: int = Field(default=7, ge=1, le=366)


class NightlyCadence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    hour_utc: int = Field(default=2, ge=0, le=23)
    window_days: int = Field(default=30, ge=1, le=366)


class WeeklyCadence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    weekday_utc: int = Field(default=0, ge=0, le=6)
    hour_utc: int = Field(default=3, ge=0, le=23)
    window_days: int = Field(default=90, ge=1, le=366)


class AnalysisCadencePolicy(BaseModel):
    """Validated policy stored below ``WorkspaceConfiguration.analysis.cadences``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["v1"] = "v1"
    post_sync: PostSyncCadence = Field(default_factory=PostSyncCadence)
    nightly: NightlyCadence = Field(default_factory=NightlyCadence)
    weekly: WeeklyCadence = Field(default_factory=WeeklyCadence)

    @classmethod
    def from_workspace_analysis(cls, analysis: object) -> "AnalysisCadencePolicy":
        if analysis is None:
            return cls()
        if not isinstance(analysis, dict):
            raise AnalysisCadencePolicyError()
        raw_cadences = analysis.get("cadences")
        if raw_cadences is None:
            return cls()
        if not isinstance(raw_cadences, dict):
            raise AnalysisCadencePolicyError()
        try:
            return cls.model_validate(raw_cadences)
        except ValidationError:
            raise AnalysisCadencePolicyError() from None

