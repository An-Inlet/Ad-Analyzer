"""Fixed read requests and minimal projection; HTTP is supplied by the caller."""

from datetime import datetime
from typing import Any, Literal, Protocol
from urllib.parse import parse_qs, urlsplit

from app.customer_context.contracts import (
    ChannelStatus,
    ContextPage,
    CustomerProvider,
    Lifecycle,
    ProfileContext,
)

# Pinned revisions verified against official references on 2026-10-06.
KLAVIYO_REVISION = "2026-07-15"
OMNISEND_REVISION = "2026-03-15"


class ReadIO(Protocol):
    def get(self, path: str, headers: dict[str, str], params: dict[str, str]) -> dict[str, Any]: ...


def status(value: object) -> ChannelStatus:
    if value in ("subscribed", "SUBSCRIBED"):
        return "subscribed"
    if value in ("unsubscribed", "UNSUBSCRIBED"):
        return "unsubscribed"
    return "unknown"


def lifecycle(value: object) -> Lifecycle:
    allowed: set[str] = {
        "subscriber",
        "lead",
        "marketingqualifiedlead",
        "salesqualifiedlead",
        "opportunity",
        "customer",
        "evangelist",
    }
    from typing import cast

    return cast(Lifecycle, value) if isinstance(value, str) and value in allowed else "unknown"


class ProfileReader:
    mode: Literal["fixture"] = "fixture"

    def __init__(self, provider: CustomerProvider, io: ReadIO) -> None:
        self.provider, self.io = provider, io

    def page(self, account_id: str, token: str, cursor: str | None, now: datetime) -> ContextPage:
        if cursor is not None and (not cursor or len(cursor) > 4096):
            raise ValueError("invalid context cursor")
        headers = {"Authorization": "Bearer " + token}
        if self.provider == "klaviyo":
            path = "https://a.klaviyo.com/api/profiles"
            headers["revision"] = KLAVIYO_REVISION
            params = {
                "page[size]": "100",
                "fields[profile]": "subscriptions",
                "additional-fields[profile]": "subscriptions",
            }
            if cursor:
                params["page[cursor]"] = cursor
        elif self.provider == "hubspot":
            path = "https://api.hubapi.com/crm/v3/objects/contacts"
            params = {"limit": "100", "properties": "lifecyclestage", "archived": "false"}
            if cursor:
                params["after"] = cursor
        else:
            path = "https://api.omnisend.com/api/contacts"
            headers["Omnisend-Version"] = OMNISEND_REVISION
            params = {"limit": "100"}
            if cursor:
                params["after"] = cursor
        payload = self.io.get(path, headers, params)
        rows = payload.get(
            {"hubspot": "results", "klaviyo": "data", "omnisend": "contacts"}[self.provider]
        )
        if not isinstance(rows, list) or len(rows) > 250:
            raise ValueError("invalid profile page")
        profiles = []
        for row in rows:
            source_id = row["id"]
            if not isinstance(source_id, str) or not source_id:
                raise ValueError("invalid source identity")
            p = ProfileContext(source_id=source_id, as_of=now)
            if self.provider == "klaviyo":
                subscriptions = row.get("attributes", {}).get("subscriptions") or {}
                for channel in ("email", "sms"):
                    marketing = subscriptions.get(channel, {}).get("marketing") or {}
                    current = status(marketing.get("consent"))
                    # Consent and suppression are distinct. List suppression must
                    # not become a channel-wide unsubscribe (nor global permission).
                    scope = "unknown"
                    if "suppression" in marketing and "list_suppressions" in marketing:
                        global_suppressed = bool(marketing["suppression"])
                        list_suppressed = bool(marketing["list_suppressions"])
                        scope = (
                            "global_and_list"
                            if global_suppressed and list_suppressed
                            else "global"
                            if global_suppressed
                            else "list"
                            if list_suppressed
                            else "none"
                        )
                    setattr(p, channel + "_suppression_scope", scope)
                    setattr(p, channel + "_status", current)
            elif self.provider == "hubspot":
                p.lifecycle = lifecycle(row.get("properties", {}).get("lifecyclestage"))
            else:
                channels: dict[str, set[ChannelStatus]] = {"email": set(), "sms": set()}
                for identifier in row.get("identifiers", []):
                    for channel, value in identifier.get("channels", {}).items():
                        if channel in channels:
                            channels[channel].add(status(value.get("status")))
                for channel, values in channels.items():
                    # Multiple addresses with conflicting statuses are not one permission.
                    setattr(
                        p,
                        channel + "_status",
                        next(iter(values)) if len(values) == 1 else "unknown",
                    )
            profiles.append(p)
        next_cursor = None
        if self.provider == "klaviyo":
            link = payload.get("links", {}).get("next")
            if link:
                parsed = urlsplit(link)
                if (
                    parsed.scheme != "https"
                    or parsed.netloc != "a.klaviyo.com"
                    or parsed.path.rstrip("/") != "/api/profiles"
                    or parsed.fragment
                ):
                    raise ValueError("untrusted continuation")
                cursors = parse_qs(parsed.query).get("page[cursor]", [])
                if len(cursors) != 1:
                    raise ValueError("invalid continuation")
                next_cursor = cursors[0]
        elif self.provider == "hubspot":
            next_cursor = payload.get("paging", {}).get("next", {}).get("after")
        else:
            paging = payload.get("paging", {})
            more = paging.get("hasMore", False)
            if type(more) is not bool:
                raise ValueError("invalid continuation")
            if more:
                next_cursor = paging.get("cursors", {}).get("after")
                if not isinstance(next_cursor, str) or not next_cursor:
                    raise ValueError("missing continuation")
        return ContextPage(
            account_id=account_id,
            profiles=profiles,
            next_cursor=str(next_cursor) if next_cursor is not None else None,
        )
