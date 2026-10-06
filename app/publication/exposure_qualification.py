"""Server-only composition of qualified portfolio facts and durable reservations.

No native cap semantics are inferred here. Deployments must supply an independently
qualified profile and a complete, owned facts reader; there is no default live reader.
The caller retains coordinator authorization and post-claim revalidation duties.
"""

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Literal

from fastapi import HTTPException
from pydantic import AwareDatetime, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.goals.schemas import StrictModel
from app.publication import execution_mandates as mandates
from app.publication.contracts import fingerprint
from app.publication.coordinator_contracts import CreationPlan
from app.publication.execution_contracts import (
    Amount,
    Environment,
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
)
from app.publication.execution_models import ProviderExecutionConsent, ProviderExposureReservation
from app.publication.provider_contracts import Digest, Id


class AccountExposureFact(StrictModel):
    account: ExecutionAccount
    reported_spend_micros: Amount
    unreported_upper_micros: Amount | None
    unchanged_future_upper_micros: Amount | None
    reporting_watermark: AwareDatetime


class PortfolioFacts(StrictModel):
    qualification_id: Id
    profile_id: str = Field(min_length=1, max_length=80)
    environment: Environment
    plan_digest: Digest
    accounts: list[AccountExposureFact] = Field(min_length=1, max_length=20)
    complete: bool
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    period_start: AwareDatetime
    period_end: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    budget_owner_key: str = Field(min_length=1, max_length=256)
    target_set_digest: Digest
    proposed_owner_upper_micros: Amount | None


class QualificationProfile(StrictModel):
    environment: Environment
    model_version: str = Field(min_length=1, max_length=80)
    semantics: Literal["qualified_native_cap", "qualified_portfolio_bound", "contract_scenario"]
    maximum_age_seconds: int = Field(strict=True, ge=1, le=300)


FactsReader = Callable[[Session, ProviderMandateBinding, CreationPlan, datetime], PortfolioFacts]


class PortfolioExposureReader:
    """Accept a server-configured cached facts source, never customer-provided proof.

    Profiles must cover the meaning of all three upper bounds, including reporting
    delay and unchanged campaigns. A daily budget alone is not such a profile.
    The source must exclude the proposed owner's future spend from unchanged_future
    to avoid duplicate counting, but include every other approved account exposure.
    """

    def __init__(
        self,
        source: FactsReader,
        profiles: Mapping[str, QualificationProfile],
        *,
        clock: Callable[[], datetime],
    ):
        self.source = source
        self.profiles = dict(profiles)
        self.clock = clock

    def __call__(
        self, db: Session, binding: ProviderMandateBinding, plan: CreationPlan, now: datetime, /
    ) -> ExposureEvidence:
        return self._read(db, binding, plan, now, None)

    def for_activation(
        self,
        db: Session,
        binding: ProviderMandateBinding,
        plan: CreationPlan,
        reservation_id: str,
        now: datetime,
        /,
    ) -> ExposureEvidence:
        return self._read(db, binding, plan, now, reservation_id)

    def _read(
        self,
        db: Session,
        binding: ProviderMandateBinding,
        plan: CreationPlan,
        now: datetime,
        retained_id: str | None,
    ) -> ExposureEvidence:
        account = ExecutionAccount.from_publication(plan.review.scope)
        consent = db.get(ProviderExecutionConsent, binding.consent_id)
        if consent is None or consent.workspace_id != account.workspace_id:
            raise HTTPException(409, "exposure authority unavailable")
        ledger, policy = mandates.checked(
            db, account.workspace_id, binding, consent.actor, lambda: now
        )
        for scope in sorted(policy.accounts, key=lambda a: a.account.account_id):
            mandates.current_account(db, scope)
        facts = PortfolioFacts.model_validate(self.source(db, binding, plan, now).model_dump())
        now = self.clock()
        expected = {a.digest() for a in policy.accounts}
        actual = [f.account.digest() for f in facts.accounts]
        if (
            facts.environment != binding.environment
            or facts.plan_digest != plan.digest()
            or facts.currency != policy.currency
            or (facts.period_start, facts.period_end) != (policy.starts_at, policy.ends_at)
            or len(set(actual)) != len(actual)
            or not set(actual).issubset(expected)
            or not facts.observed_at <= now < facts.expires_at
            or any(f.reporting_watermark > facts.observed_at for f in facts.accounts)
        ):
            raise HTTPException(409, "portfolio facts lineage or time unavailable")
        held = list(
            db.scalars(
                select(ProviderExposureReservation)
                .where(
                    ProviderExposureReservation.workspace_id == policy.workspace_id,
                    ProviderExposureReservation.environment == binding.environment,
                    ProviderExposureReservation.state == "held",
                )
                .order_by(ProviderExposureReservation.id)
                .limit(10001)
                .with_for_update()
            )
        )
        if len(held) > 10000:
            raise HTTPException(409, "portfolio reservation inventory exceeds bound")
        if retained_id is not None:
            retained = next((r for r in held if r.id == retained_id), None)
            if (
                retained is None
                or retained.ledger_id != ledger.id
                or retained.budget_owner_key != facts.budget_owner_key
                or retained.amount_micros != facts.proposed_owner_upper_micros
            ):
                raise HTTPException(409, "exact retained exposure unavailable")
        reserved = sum(r.amount_micros for r in held if r.id != retained_id)
        reported = sum(f.reported_spend_micros for f in facts.accounts)
        profile = self.profiles.get(facts.profile_id)
        complete = facts.complete and set(actual) == expected
        qualified = (
            complete
            and profile is not None
            and profile.environment == binding.environment
            and not (binding.environment == "live" and profile.semantics == "contract_scenario")
            and (now - facts.observed_at).total_seconds()
            <= min(policy.freshness_seconds, profile.maximum_age_seconds)
            and reported >= ledger.spent_high_water_micros
            and facts.proposed_owner_upper_micros is not None
            and all(
                f.unreported_upper_micros is not None
                and f.unchanged_future_upper_micros is not None
                for f in facts.accounts
            )
        )
        unreported = (
            sum(f.unreported_upper_micros or 0 for f in facts.accounts) if qualified else None
        )
        unchanged = (
            sum(f.unchanged_future_upper_micros or 0 for f in facts.accounts) if qualified else None
        )
        total = (
            reported + reserved + unreported + unchanged + facts.proposed_owner_upper_micros
            if qualified
            and unreported is not None
            and unchanged is not None
            and facts.proposed_owner_upper_micros is not None
            else None
        )
        return ExposureEvidence(
            environment=binding.environment,
            mandate=binding,
            account=account,
            covered_account_ids=[a.account.account_id for a in policy.accounts],
            budget_owner_key=facts.budget_owner_key,
            target_set_digest=facts.target_set_digest,
            state_digest=fingerprint("inlet.portfolio-facts.v1", facts.model_dump(mode="json")),
            currency=policy.currency,
            period_start=policy.starts_at,
            period_end=policy.ends_at,
            observed_at=facts.observed_at,
            expires_at=min(
                facts.expires_at,
                facts.observed_at
                + timedelta(seconds=min(policy.freshness_seconds, profile.maximum_age_seconds)),
            )
            if qualified and profile
            else facts.expires_at,
            reporting_watermark=min(f.reporting_watermark for f in facts.accounts),
            completeness="complete" if complete else "incomplete",
            qualification_id=facts.qualification_id,
            model_version=profile.model_version if profile else "unqualified",
            cap_semantics=profile.semantics if qualified and profile else "unqualified",
            reported_spend_micros=reported,
            unreported_upper_micros=unreported,
            unchanged_future_upper_micros=unchanged,
            proposed_owner_upper_micros=facts.proposed_owner_upper_micros if qualified else None,
            existing_reservations_micros=reserved,
            portfolio_upper_micros=total,
        )
