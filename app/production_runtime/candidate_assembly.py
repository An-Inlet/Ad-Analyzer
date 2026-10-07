"""Per-original-session candidate composition; no automatic authority or producer."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.commerce.evidence import lock_workspace, read_publication
from app.commerce.models import CommerceMeasurementPublication
from app.commerce.publication_contracts import V1
from app.customers.access import CustomerPrincipal, lock_customer_mutation
from app.customers.identity import IdentityProvider
from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.optimization_candidates import service
from app.optimization_candidates.contracts import (
    CandidateEvidence,
    CandidateObservation,
    CandidateScope,
    SourceFence,
)
from app.optimization_candidates.review_bridge import CandidateReviewRuntime
from app.optimization_candidates.selection import CandidateSelectionRuntime, SelectionReadRequest
from app.production_runtime.candidate_configuration import (
    CandidateConfigurationError,
    CandidatePolicyBundleV1,
    load_candidate_configuration,
    validate_candidate_source,
)
from app.production_runtime.candidate_sources import (
    registered_candidate_source,
    validate_candidate_binding,
)
from app.production_runtime.optimization_assembly import configured_optimization, pinned
from app.publication import customer_optimization, execution_mandates
from app.publication.customer_optimization_contracts import (
    CustomerOptimizationRuntime,
    TargetRequest,
)
from app.publication.execution_contracts import ProviderMandateBinding
from app.settings import Settings


def unavailable() -> HTTPException:
    return HTTPException(409, "candidate_configuration_unavailable")


@dataclass(frozen=True)
class CandidateRuntimeBundle:
    candidate: service.CandidateRuntime
    review: CandidateReviewRuntime
    policies: CandidatePolicyBundleV1
    owned: "OwnedCandidateReads"
    automatic_unavailable_reason: str = "first_decision_producer_unavailable"

    def selection_for(self, binding: ProviderMandateBinding) -> CandidateSelectionRuntime:
        binding = ProviderMandateBinding.model_validate(binding.model_dump())
        return CandidateSelectionRuntime(
            self.candidate,
            lambda request, now: self.owned.catalog(request, now, binding),
            self.owned.source_fence,
            self.candidate.clock,
        )


class OwnedCandidateReads:
    def __init__(
        self,
        engine: Engine,
        principal: CustomerPrincipal,
        identity: IdentityProvider,
        runtime: CustomerOptimizationRuntime,
        source_schema: str,
    ) -> None:
        self.engine, self.principal, self.identity = engine, principal, identity
        self.sessions = sessionmaker(engine)
        self.runtime, self.source_schema = runtime, source_schema

    def authorize(self, db: Session, wid: int) -> None:
        lock_customer_mutation(db, self.principal, wid, self.identity)
        self.runtime.execution.authorize(db, wid, self.principal.user.id)

    def catalog(self, request: TargetRequest, now: datetime, binding: ProviderMandateBinding):  # type: ignore[no-untyped-def]
        configured = self.runtime.configured
        if configured is None:
            raise unavailable()
        # Configured catalog uses its own private sessions and releases them before IO.
        return configured.catalog(request, now, original_mandate=binding)

    def source_fence(
        self, caller: Session, request: SelectionReadRequest, now: datetime
    ) -> SourceFence:
        if caller.get_bind() is not self.engine:
            raise unavailable()
        wid = request.target_request.scope.workspace_id
        with self.sessions() as db:
            self.authorize(db, wid)
            _, policy = execution_mandates.checked(
                db, wid, request.mandate, self.principal.user.id, self.runtime.clock
            )
            goal = goals.owned(db, wid, request.target_request.goal_id)
            goals.expect(goal, request.target_request.goal_revision)
            if policy.goal_id != goal.id or policy.goal_revision != goal.revision:
                raise unavailable()
            definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
            document = read_publication(db, wid, definition.store_id, now=self.runtime.clock())
            row = db.get(CommerceMeasurementPublication, document["publication_id"])
            workspace = lock_workspace(db, wid, active=True)
            if row is None or row.manifest.get("schema_version") != V1:
                raise unavailable()
            result = SourceFence(
                workspace_privacy_revision=workspace.export_privacy_revision,
                store_id=row.store_id,
                publication_id=row.id,
                generation=row.generation,
                privacy_epoch=row.privacy_epoch,
                publication_revision=row.publication_revision,
                source_revision=row.source_revision,
                manifest_digest=row.manifest_digest,
            )
            self.authorize(db, wid)
            return result

    def read(self, caller: Session, scope: CandidateScope, now: datetime) -> CandidateObservation:
        if caller.get_bind() is not self.engine:
            raise unavailable()
        wid = scope.account.workspace_id
        # Never commit/rollback caller. Only these short private sessions own locks.
        with self.sessions() as db:
            self.authorize(db, wid)
            service.source_current(db, scope, self.principal.user.id)
        request = TargetRequest(
            goal_id=scope.goal_id,
            goal_revision=scope.goal_revision,
            goal_digest=scope.goal_digest,
            scope=scope.account,
        )
        catalog = self.catalog(request, now, scope.mandate)
        matches = [
            o.state
            for o in catalog.options
            if o.state.target == scope.target
            and o.state.budget_owner.key(scope.account) == scope.budget_owner_key
            and o.state.budget_owner.target_set_digest() == scope.target_set_digest
        ]
        fresh = self.runtime.clock()
        if (
            not catalog.complete
            or len(matches) != 1
            or not catalog.observed_at <= fresh < catalog.expires_at
        ):
            raise unavailable()
        with self.sessions() as db:
            self.authorize(db, wid)
            service.source_current(db, scope, self.principal.user.id)
        return CandidateObservation(
            scope=scope,
            state=matches[0],
            evidence=CandidateEvidence(
                scope_digest=scope.digest(),
                source_schema=self.source_schema,
                source_digest=scope.source.manifest_digest,
                source_reference=scope.source.publication_id,
                qualification="unqualified",
                direction="none",
                observation_count=None,
                observed_at=catalog.observed_at,
                expires_at=min(catalog.expires_at, catalog.observed_at + timedelta(minutes=5)),
            ),
        )


@contextmanager
def configured_candidates(
    db: Session,
    principal: CustomerPrincipal,
    identity: IdentityProvider,
    configuration: Settings,
    *,
    existing_native: CustomerOptimizationRuntime | None = None,
) -> Iterator[CandidateRuntimeBundle | None]:
    values = (
        configuration.candidate_assembly_manifest_path,
        configuration.candidate_assembly_manifest_digest,
        configuration.candidate_policy_bundle_path,
    )
    if not any(values):
        yield None
        return
    try:
        optimization = pinned(
            configuration.optimization_execution_manifest_path,
            configuration.optimization_execution_manifest_digest,
            configuration.optimization_operating_policy_path,
        )
        if optimization is None:
            raise unavailable()
        parsed = load_candidate_configuration(*values, optimization_manifest=optimization[0])
        if parsed is None:
            raise unavailable()
        manifest, policies = parsed
        registered = registered_candidate_source(manifest.evidence_source_id)
        if registered is None or manifest.mode != "candidates_only":
            yield None
            return
        validate_candidate_source(manifest, policies, registered.descriptor)
    except (CandidateConfigurationError, ValueError):
        raise unavailable() from None
    engine = db.get_bind()
    if not isinstance(engine, Engine):
        raise unavailable()
    with ExitStack() as stack:
        raw = existing_native
        if raw is None:
            raw = stack.enter_context(
                configured_optimization(db, principal, identity, configuration)
            )
        if raw is None:
            yield None
            return
        native = customer_optimization.bind(raw, principal, identity)
        owned = OwnedCandidateReads(
            engine, principal, identity, native, registered.descriptor.source_schema
        )

        def policy_reader(session: Session, wid: int, identifier: str, revision: int):  # type: ignore[no-untyped-def]
            return next(
                (
                    p.as_policy()
                    for p in policies.candidate_policies
                    if (p.workspace_id, p.policy_id, p.revision) == (wid, identifier, revision)
                ),
                None,
            )

        base = service.CandidateRuntime(
            manifest.environment, identity, owned.read, policy_reader, native.clock
        )
        binding = registered.build(base, principal, identity, native.clock)
        validate_candidate_binding(registered.descriptor, binding)
        candidate = replace(
            base,
            learning_profiles=frozenset(
                (p.source_schema, p.profile, p.revision, p.digest)
                for p in registered.descriptor.qualified_profiles
            ),
            feedback_dependent_schemas=frozenset({registered.descriptor.source_schema})
            if registered.descriptor.feedback_dependent
            else frozenset(),
            authorized_evidence_transform=binding.authorized_transform,
            authorized_final_evidence_current=binding.authorized_final_current,
        )
        yield CandidateRuntimeBundle(
            candidate,
            CandidateReviewRuntime(candidate, native.execution, native.clock),
            policies,
            owned,
        )


@contextmanager
def candidate_job_runtime(
    engine: Engine,
    workspace_id: int,
    job_id: str,
    identity: IdentityProvider,
    configuration: Settings,
    *,
    existing_native: CustomerOptimizationRuntime | None = None,
) -> Iterator[CandidateRuntimeBundle | None]:
    with Session(engine) as db:
        lock_workspace(db, workspace_id, active=True)
        row = service.load(db, workspace_id, job_id)
        principal = service.principal_for(db, row)
        lock_customer_mutation(db, principal, workspace_id, identity)
        # End only this owned admission session's transaction before any provider IO.
        db.commit()
        with configured_candidates(db, principal, identity, configuration) as bundle:
            yield bundle


def run_configured_candidate_reads(engine: Engine, configuration: Settings) -> dict[str, int]:
    if not configuration.customer_candidate_reads_enabled:
        return {}
    from app.automation import AutomationControlKey, AutomationControlService
    from app.customers.identity import get_identity_provider
    from app.publication.clock import utc_now

    with Session(engine) as db:
        if not AutomationControlService(db).master_enabled(AutomationControlKey.ALL_DATA_SYNCS):
            return {}
    values = (
        configuration.candidate_assembly_manifest_path,
        configuration.candidate_assembly_manifest_digest,
        configuration.candidate_policy_bundle_path,
    )
    if not any(values):
        return {}
    optimization = pinned(
        configuration.optimization_execution_manifest_path,
        configuration.optimization_execution_manifest_digest,
        configuration.optimization_operating_policy_path,
    )
    if optimization is None:
        return {}
    parsed = load_candidate_configuration(*values, optimization_manifest=optimization[0])
    if parsed is None:
        return {}
    manifest, policies = parsed
    source = registered_candidate_source(manifest.evidence_source_id)
    if source is None or manifest.mode != "candidates_only":
        return {}
    validate_candidate_source(manifest, policies, source.descriptor)
    identity = get_identity_provider()

    @contextmanager
    def owned(
        selected_engine: Engine, wid: int, identifier: str
    ) -> Iterator[service.CandidateRuntime | None]:
        with candidate_job_runtime(
            selected_engine, wid, identifier, identity, configuration
        ) as bundle:
            yield bundle.candidate if bundle else None

    return service.run_candidate_reads(
        engine, scoped_provider=owned, environment=manifest.environment, clock=utc_now
    )
