"""Named, bounded server catalog; customer input never supplies provider resource proof."""

import json
from datetime import datetime, timedelta
from typing import Protocol

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount
from app.publication.provider_contracts import Digest, Id


class GoogleCatalogRequest(StrictModel):
    account: ExecutionAccount
    draft_id: Id
    draft_revision: int = Field(strict=True, ge=1)
    source_digest: Digest
    countries: list[str] = Field(min_length=1, max_length=20)
    languages: list[str] = Field(min_length=1, max_length=10)

    def digest(self) -> str:
        return fingerprint("inlet.google-catalog-request.v1", self.model_dump(mode="json"))


class GoogleCatalogOption(StrictModel):
    """Owned references are discovered by the server, then independently qualified."""

    label: str = Field(min_length=1, max_length=160)
    custom_conversion_goal: str = Field(
        pattern=r"^customers/[0-9]{10}/customConversionGoals/[0-9]+$"
    )
    conversion_actions: list[str] = Field(min_length=1, max_length=20)
    country_targets: dict[str, str] = Field(min_length=1, max_length=20)
    language_targets: dict[str, str] = Field(min_length=1, max_length=10)

    def identifier(self, request: GoogleCatalogRequest) -> str:
        # Stable across refresh timestamps but changes with source/scope/option content.
        return fingerprint(
            "inlet.google-catalog-option.v1",
            {"request": request.digest(), "option": self.model_dump(mode="json")},
        )


class GoogleCatalog(StrictModel):
    request: GoogleCatalogRequest
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    options: list[GoogleCatalogOption] = Field(max_length=50)
    unavailable_reasons: list[str] = Field(max_length=20)

    @model_validator(mode="after")
    def bounded(self) -> "GoogleCatalog":
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5):
            raise ValueError("catalog lifetime exceeds bound")
        if len(json.dumps(self.model_dump(mode="json")).encode()) > 65536:
            raise ValueError("catalog exceeds byte bound")
        ids = [option.identifier(self.request) for option in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate catalog option")
        prefix = f"customers/{self.request.account.external_advertiser_id}/"
        for option in self.options:
            if (
                not option.custom_conversion_goal.startswith(prefix)
                or any(
                    not action.startswith(prefix + "conversionActions/")
                    for action in option.conversion_actions
                )
                or set(option.country_targets) != set(self.request.countries)
                or set(option.language_targets) != set(self.request.languages)
            ):
                raise ValueError("catalog references do not match exact owned request")
        return self


class GoogleCatalogReader(Protocol):
    def __call__(self, request: GoogleCatalogRequest, now: datetime, /) -> GoogleCatalog:
        """Read-only bounded discovery; no DB transaction or customer-controlled credentials."""
        ...
