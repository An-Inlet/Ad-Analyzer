"""Original-session-owned Meta vault assembly with private database transactions."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

import httpx
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign
from app.automation.catalog import AutomationControlKey
from app.automation.service import AutomationControlService
from app.billing.entitlements import paid_work
from app.collectors.account_diagnostics import _BorrowedTransport
from app.collectors.meta_budget import MetaBudgetHTTP, NativeBudgetContext, NativeBudgetUnavailable
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.goals import service as goals
from app.initial_planning.native_budget_contracts import NativeBudgetRequestV1
from app.meta.models import MetaConnection
from app.meta.security import Vault
from app.planning_reporting.contracts import PlanningReportingProfileV1
from app.publication import customer_intents
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority
from app.settings import Settings


def native_budget_transport() -> httpx.BaseTransport:
    """Low-level transport seam; no automatic retries or environment proxies."""
    return httpx.HTTPTransport(retries=0, trust_env=False)


@contextmanager
def owned_meta_budget_reader(
    sessions: Callable[[], Session],
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    profile: PlanningReportingProfileV1,
    configuration: Settings,
    *,
    clock: Callable[[], datetime],
) -> Iterator[MetaBudgetHTTP]:
    """Capture only this original principal. No shared owner or global DB engine."""
    authorize = bind_authority(principal, provider)
    actor = principal.user.id

    def context(request: NativeBudgetRequestV1, now: datetime) -> NativeBudgetContext:
        wid = request.scope.workspace_id
        if request.profile_digest != profile.digest() or request.environment != profile.environment:
            raise NativeBudgetUnavailable("native_budget_profile_changed")
        with sessions() as db:
            authorize(db, wid, actor)
            if not AutomationControlService(db).master_enabled(AutomationControlKey.ALL_DATA_SYNCS):
                raise NativeBudgetUnavailable("native_budget_reads_paused")
            paid_work(db, wid, now)
            scope = customer_intents.account(db, wid, request.cohort.account_id)
            if scope.model_dump() != request.scope.model_dump():
                raise NativeBudgetUnavailable("native_budget_account_changed")
            goal = goals.owned(db, wid, request.goal_id)
            goals.expect(goal, request.goal_revision)
            if (
                goals.assessment(db, goal, now) != "confirmed"
                or fingerprint(
                    "inlet.optimization-goal.v1",
                    {
                        "definition": goals.current(db, goal).definition,
                    },
                )
                != request.goal_digest
            ):
                raise NativeBudgetUnavailable("native_budget_goal_changed")
            account = db.get(AdvertisingAccount, request.cohort.account_id)
            campaign = db.get(Campaign, request.cohort.campaign_id)
            if (
                account is None
                or campaign is None
                or campaign.account_id != request.cohort.account_id
                or campaign.platform.value != "meta_ads"
                or campaign.external_campaign_id != request.target.external_id
                or (account.currency_code, account.time_zone)
                != (
                    request.cohort.currency,
                    request.cohort.time_zone,
                )
                or request.cohort.selected_event != profile.windows.selected_event
                or request.cohort.query_version != profile.windows.query_version
            ):
                raise NativeBudgetUnavailable("native_budget_cohort_changed")
            source = db.scalar(
                select(MetaConnection).where(
                    MetaConnection.workspace_id == wid,
                    MetaConnection.account_id == scope.account.account_id,
                    MetaConnection.workspace_integration_id == scope.account.connection_id,
                )
            )
            if source is None or not source.encrypted_credentials:
                raise NativeBudgetUnavailable("native_budget_credential_unavailable")
            if source.conversion_action_type != request.cohort.selected_event:
                raise NativeBudgetUnavailable("native_budget_cohort_changed")
            bundle = Vault(configuration).open(
                wid, source.external_account_id, source.encrypted_credentials
            )
            raw, raw_expiry = bundle.get("access_token"), bundle.get("expires_at")
            try:
                if (
                    not isinstance(raw, str)
                    or not 1 <= len(raw) <= 16384
                    or not isinstance(raw_expiry, str)
                ):
                    raise ValueError()
                expiry = datetime.fromisoformat(raw_expiry)
                if expiry.tzinfo is None or expiry <= now + timedelta(
                    seconds=profile.native_read.credential_minimum_remaining_seconds
                ):
                    raise ValueError()
            except ValueError:
                raise NativeBudgetUnavailable("native_budget_credential_unavailable") from None
            authorize(db, wid, actor)
            # Exiting the private session releases every lock before HTTP starts.
            return NativeBudgetContext(
                request_digest=request.digest(),
                access_token=SecretStr(raw),
                app_secret=configuration.meta_client_secret,
                expires_at=expiry,
                label=campaign.name[:200] or "Owned Campaign",
            )

    transport = native_budget_transport()
    try:
        yield MetaBudgetHTTP(
            context, profile.native_read, transport=_BorrowedTransport(transport), clock=clock
        )
    finally:
        transport.close()
