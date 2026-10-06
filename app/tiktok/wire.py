"""Injected-IO TikTok API v1.3 read adapter; never instantiated by runtime defaults."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlencode

from pydantic import SecretStr

from app.sources.contracts import AdvertisingPage, SourceAccount, SourceGrant

IO = Callable[[str, str, dict[str, Any], str | None], dict[str, Any]]
PHASES = ("campaigns", "groups", "ads", "campaign_metrics", "group_metrics", "ad_metrics")


class TikTokReadAdapter:
    mode: Literal["fixture", "provider_read"] = "fixture"

    def __init__(self, io: IO, app_id: str, secret: SecretStr) -> None:
        self.io, self.app_id, self.secret = io, app_id, secret

    def _call(
        self, method: str, path: str, params: dict[str, Any], token: str | None = None
    ) -> dict[str, Any]:
        result = self.io(method, "/open_api/v1.3/" + path + "/", params, token)
        if result.get("code") != 0 or not isinstance(result.get("data"), dict):
            raise ValueError("TikTok read unavailable")
        return dict(result["data"])

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        return "https://business-api.tiktok.com/portal/auth?" + urlencode(
            {"app_id": self.app_id, "state": state, "redirect_uri": redirect_uri}
        )

    def exchange(self, code: str, redirect_uri: str) -> SourceGrant:
        grant = self._call(
            "POST",
            "oauth2/access_token",
            {"app_id": self.app_id, "secret": self.secret.get_secret_value(), "auth_code": code},
        )
        token = grant.get("access_token")
        ids = grant.get("advertiser_ids")
        if (
            not isinstance(token, str)
            or not 1 <= len(token) <= 8192
            or not isinstance(ids, list)
            or not 1 <= len(ids) <= 100
        ):
            raise ValueError("TikTok advertiser grant unavailable")
        if any(not isinstance(i, str) or not i.isdigit() or len(i) > 32 for i in ids):
            raise ValueError("invalid advertiser identifiers")
        data = self._call(
            "GET",
            "advertiser/info",
            {"advertiser_ids": ids, "fields": ["advertiser_id", "name", "currency", "timezone"]},
            token,
        )
        if (
            not isinstance(data.get("list"), list)
            or len(data["list"]) != len(ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("incomplete advertiser metadata")
        accounts = []
        seen: set[str] = set()
        for account in data["list"]:
            if account["advertiser_id"] in seen:
                raise ValueError("duplicate advertiser metadata")
            seen.add(account["advertiser_id"])
            if account["advertiser_id"] not in ids:
                raise ValueError("advertiser not in grant")
            accounts.append(
                SourceAccount(
                    external_id=account["advertiser_id"],
                    name=account["name"],
                    currency=account["currency"],
                    time_zone=account["timezone"],
                )
            )
        return SourceGrant(access_token=SecretStr(token), accounts=accounts)

    def read(
        self, account: str, token: str, start: date, end: date, cursor: str | None
    ) -> dict[str, Any]:
        if not account.isdigit() or len(account) > 32:
            raise ValueError("invalid advertiser")
        phase, number = cursor.split(":", 1) if cursor else ("campaigns", "1")
        if phase not in PHASES or not number.isdigit() or not 1 <= int(number) <= 100:
            raise ValueError("invalid TikTok cursor")
        params: dict[str, Any] = {"advertiser_id": account, "page": int(number), "page_size": 100}
        account_data = self._call(
            "GET",
            "advertiser/info",
            {"advertiser_ids": [account], "fields": ["advertiser_id", "currency"]},
            token,
        )
        if len(account_data["list"]) != 1 or account_data["list"][0]["advertiser_id"] != account:
            raise ValueError("advertiser metadata mismatch")
        result: dict[str, Any] = {
            "account_id": account,
            "currency": account_data["list"][0]["currency"],
        }
        if phase in {"campaigns", "groups", "ads"}:
            edge = {"campaigns": "campaign/get", "groups": "adgroup/get", "ads": "ad/get"}[phase]
        else:
            edge = "report/integrated/get"
            level, idfield = {
                "campaign_metrics": ("AUCTION_CAMPAIGN", "campaign_id"),
                "group_metrics": ("AUCTION_ADGROUP", "adgroup_id"),
                "ad_metrics": ("AUCTION_AD", "ad_id"),
            }[phase]
            params.update(
                report_type="BASIC",
                data_level=level,
                dimensions=[idfield, "stat_time_day"],
                metrics=["impressions", "clicks", "spend", "conversion"],
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                enable_total_metrics=False,
            )
        response = self._call("GET", edge, params, token)
        rows = response.get("list")
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("invalid TikTok page")
        inventory = []
        for row in rows:
            if row.get("advertiser_id", account) != account:
                raise ValueError("cross-advertiser row")
            if phase == "campaigns":
                if row.get("advertiser_id", account) != account:
                    raise ValueError("cross-advertiser campaign")
                inventory.append(
                    {
                        "id": row["campaign_id"],
                        "name": row["campaign_name"],
                        "status": row["operation_status"],
                        "objective": row["objective_type"],
                    }
                )
            elif phase == "groups":
                inventory.append(
                    {
                        "id": row["adgroup_id"],
                        "campaign_id": row["campaign_id"],
                        "name": row["adgroup_name"],
                        "status": row["operation_status"],
                    }
                )
            elif phase == "ads":
                inventory.append(
                    {
                        "id": row["ad_id"],
                        "group_id": row["adgroup_id"],
                        "name": row["ad_name"],
                        "status": row["operation_status"],
                    }
                )
            else:
                dims, values = row["dimensions"], row["metrics"]
                grain, key = {
                    "campaign_metrics": ("campaign", "campaign_id"),
                    "group_metrics": ("ad_group", "adgroup_id"),
                    "ad_metrics": ("ad", "ad_id"),
                }[phase]
                inventory.append(
                    {
                        "level": grain,
                        "id": dims[key],
                        "day": dims["stat_time_day"][:10],
                        "impressions": int(values["impressions"]),
                        "clicks": int(values["clicks"]),
                        "cost_micros": int(Decimal(values["spend"]) * 1_000_000),
                        "conversions": values["conversion"],
                        "conversion_value_micros": 0,
                    }
                )  # Value/goal semantics remain unavailable, not canonical sales.
        result[phase if phase in {"campaigns", "groups", "ads"} else "metrics"] = inventory
        info = response.get("page_info", {})
        total = info.get("total_page")
        if (
            type(total) is not int
            or not 0 <= total <= 100
            or type(info.get("page", int(number))) is not int
            or info.get("page", int(number)) != int(number)
            or (total == 0 and bool(rows))
            or (total > 0 and int(number) > total)
        ):
            raise ValueError("invalid TikTok pagination")
        if int(number) < total:
            result["next_cursor"] = phase + ":" + str(int(number) + 1)
        elif phase != PHASES[-1]:
            result["next_cursor"] = PHASES[PHASES.index(phase) + 1] + ":1"
        return AdvertisingPage.model_validate(result).model_dump(mode="json")
