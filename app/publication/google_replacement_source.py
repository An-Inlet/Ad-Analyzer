"""Disabled-by-default composition, not a provider financial bound producer."""

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.publication import execution_mandates as mandates
from app.publication.contracts import fingerprint
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ProviderMandateBinding
from app.publication.execution_models import ProviderExposureReservation
from app.publication.google_completion import read_owned
from app.publication.google_request_terminal import read_terminal_batch
from app.publication.optimization_contracts import OptimizationIntent, OptimizationState
from app.publication.optimization_execution_contracts import (
    OptimizationPlan,
    OptimizationQualification,
    positive_delta,
)
from app.publication.replacement_contracts import ReplacementEvidence, ReplacementSnapshot
from app.publication.transition_source_contracts import (
    TransitionCertificate,
    TransitionCertificateReader,
    TransitionProfile,
    TransitionSourceRequest,
)


class GoogleReplacementReader:
    """Server binds current customer/session authorizer and trusted source explicitly.

    Each private session closes before external source IO. Caller session is untouched.
    No source caching, financial mutation, profile discovery or runtime registration.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        actor: str,
        authorize: ExecutionAuthorizer,
        transition_reader: TransitionCertificateReader,
        allowed_profiles: Mapping[tuple[str, int], TransitionProfile],
        clock: Callable[[], datetime],
    ) -> None:
        self.sessions, self.actor, self.authorize = session_factory, actor, authorize
        self.source, self.clock = transition_reader, clock
        self.profiles = {
            key: TransitionProfile.model_validate(value.model_dump())
            for key, value in allowed_profiles.items()
        }

    def _check(
        self, request: TransitionSourceRequest, certificate: TransitionCertificate | None
    ) -> ReplacementEvidence | None:
        now = self.clock()
        s, i, q = request.snapshot, request.intent, request.qualification
        with self.sessions() as db:
            batch = read_terminal_batch(
                db, s.workspace_id, request.binding, s, self.actor, now, authorize=self.authorize
            )
            ledger, policy = mandates.checked(
                db, s.workspace_id, request.binding, self.actor, lambda: now
            )
            if (
                request.binding != i.mandate
                or i.scope != s.account
                or i.expected_state_digest != request.before.digest()
                or i.approved_target_set_digest != s.target_set_digest
                or request.before.budget_owner.key(s.account) != s.budget_owner_key
                or not q.observed_at <= now < q.expires_at
                or q.unresolved
            ):
                raise ValueError("transition request changed")
            if certificate is None:
                return None
            c = certificate
            profile = self.profiles.get((c.source_profile, c.source_revision))
            e = c.portfolio
            if (
                profile is None
                or profile.environment != s.environment
                or profile.qualification_profile != q.profile
                or profile.qualification_revision != q.qualification_revision
                or profile.cap_semantics != e.cap_semantics
                or profile.model_version != e.model_version
                or c.request_digest != request.digest()
                or not c.observed_at <= now < c.expires_at
                or c.observed_at < q.observed_at
                or c.observed_at < request.before.observed_at
                or e.observed_at != c.observed_at
                or e.expires_at != c.expires_at
                or e.state_digest != request.before.digest()
                or e.reported_spend_micros < ledger.spent_high_water_micros
                or not e.eligible(policy, now)
            ):
                raise ValueError("current qualified transition certificate unavailable")
            held = (
                db.scalar(
                    select(
                        func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)
                    ).where(
                        ProviderExposureReservation.workspace_id == s.workspace_id,
                        ProviderExposureReservation.environment == s.environment,
                        ProviderExposureReservation.state == "held",
                        ProviderExposureReservation.id != s.predecessor_id,
                    )
                )
                or 0
            )
            if e.existing_reservations_micros != held:
                raise ValueError("current portfolio holds changed")
            for receipt in s.receipts:
                document = read_owned(db, s.workspace_id, receipt.attempt_id, self.actor, now)
                if document is None or document.recorded_at > c.observed_at:
                    raise ValueError("completion postdates transition certificate")
            # Stable content, not the fresh read's authorization timestamp. Never extends expiry.
            closure = fingerprint(
                "inlet.google-original-terminal-content.v1",
                {
                    "profile": batch.profile,
                    "account": batch.account.model_dump(mode="json"),
                    "mandate": batch.mandate.model_dump(mode="json"),
                    "snapshot_digest": batch.snapshot_digest,
                    "closed_requests": [x.model_dump(mode="json") for x in batch.closed_requests],
                },
            )
            proof = ReplacementEvidence(
                snapshot_digest=s.digest(),
                intent_digest=i.digest(),
                environment=s.environment,
                qualification_profile=c.source_profile,
                qualification_revision=c.source_revision,
                proof_kind=profile.proof_kind,
                observed_at=c.observed_at,
                expires_at=min(
                    c.expires_at,
                    q.expires_at,
                    c.observed_at + timedelta(seconds=policy.freshness_seconds),
                ),
                closed_requests=batch.closed_requests,
                closure_evidence_digest=closure,
                transition_evidence_digest=c.digest(),
                transition_semantics=c.semantics,
                portfolio=e,
                unresolved=[],
            )
            proof.bind(s, i)
            if not proof.observed_at <= now < proof.expires_at:
                raise ValueError("composed evidence expired")
            OptimizationPlan(
                intent=i,
                before=request.before,
                qualification=q,
                exposure=e,
                positive_change_micros=positive_delta(i, request.before),
            )
            # Locks/authorization can wait. Sample after them rather than returning
            # an epoch that expired while this transaction acquired authority.
            self.authorize(db, s.workspace_id, self.actor)
            _, final_policy = mandates.checked(
                db, s.workspace_id, request.binding, self.actor, self.clock
            )
            final_now = self.clock()
            batch.bind(s, request.binding, final_now)
            if (
                final_policy != policy
                or not q.observed_at <= final_now < q.expires_at
                or not proof.observed_at <= final_now < proof.expires_at
                or not e.eligible(final_policy, final_now)
            ):
                raise ValueError("composed evidence expired during authorization")
            return proof

    def __call__(
        self,
        db: Session,
        binding: ProviderMandateBinding,
        intent: OptimizationIntent,
        before: OptimizationState,
        qualification: OptimizationQualification,
        snapshot: ReplacementSnapshot,
        now: datetime,
        /,
    ) -> ReplacementEvidence:
        try:
            request = TransitionSourceRequest.model_validate(
                {
                    "binding": binding.model_dump(),
                    "intent": intent.model_dump(),
                    "before": before.model_dump(),
                    "qualification": qualification.model_dump(),
                    "snapshot": snapshot.model_dump(),
                }
            )
            self._check(request, None)
            try:
                raw = self.source(request.model_copy(deep=True), self.clock())
            except Exception:
                raise HTTPException(409, "qualified transition source unavailable") from None
            certificate = TransitionCertificate.model_validate(raw.model_dump())
            result = self._check(request, certificate)
            assert result is not None
            return result
        except HTTPException:
            raise
        except Exception:
            # Source errors contain no safe provider/customer payload contract.
            raise HTTPException(409, "qualified replacement evidence unavailable") from None
