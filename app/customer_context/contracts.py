from datetime import datetime
from typing import Literal, Protocol

from pydantic import AwareDatetime, ConfigDict, Field, SecretStr

from app.goals.schemas import StrictModel

CustomerProvider = Literal["klaviyo", "hubspot", "omnisend"]
ChannelStatus = Literal["subscribed", "unsubscribed", "unknown"]
Lifecycle = Literal[
    "subscriber",
    "lead",
    "marketingqualifiedlead",
    "salesqualifiedlead",
    "opportunity",
    "customer",
    "evangelist",
    "unknown",
]


class ProfileContext(StrictModel):
    source_id: str = Field(min_length=1, max_length=128)
    email_status: ChannelStatus = "unknown"
    sms_status: ChannelStatus = "unknown"
    email_suppression_scope: Literal["unknown", "none", "list", "global", "global_and_list"] = (
        "unknown"
    )
    sms_suppression_scope: Literal["unknown", "none", "list", "global", "global_and_list"] = (
        "unknown"
    )
    lifecycle: Lifecycle = "unknown"
    as_of: AwareDatetime


class ContextPage(StrictModel):
    account_id: str = Field(min_length=1, max_length=128)
    profiles: list[ProfileContext] = Field(max_length=250)
    next_cursor: str | None = Field(default=None, max_length=4096)


class VerifiedCustomerMapping(StrictModel):
    source_id: str = Field(min_length=1, max_length=128)
    shopify_customer_id: str = Field(pattern=r"^(gid://shopify/Customer/)?[0-9]{1,32}$")
    shop_key: str = Field(pattern=r"^[a-f0-9]{64}$")


class ContextReader(Protocol):
    @property
    def mode(self) -> Literal["fixture", "provider_read"]: ...

    provider: CustomerProvider

    def page(
        self, account_id: str, token: str, cursor: str | None, now: datetime
    ) -> ContextPage: ...


class FixtureIdentityMapping:
    """Deliberately concrete offline proof source; not a live custom-property matcher."""

    def __init__(self, mappings: list[VerifiedCustomerMapping]) -> None:
        self.mappings = {m.source_id: m for m in mappings}
        if len(self.mappings) != len(mappings):
            raise ValueError("duplicate source identity mapping")


class RefreshCandidate(StrictModel):
    """Unverified renewal credentials; never authorize profile reads with this object."""

    model_config = ConfigDict(frozen=True)
    provider: CustomerProvider
    access_token: SecretStr
    refresh_token: SecretStr | None = None
    expires_at: AwareDatetime | None = None
    scopes: frozenset[str] | None = None
