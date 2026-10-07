"""Request-owned lazy optimization assembly; no financial evidence ships enabled."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import datetime
from functools import lru_cache

import httpx
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.collectors.account_diagnostics import _BorrowedTransport
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.executors.google_optimization import GoogleOptimizationTransport
from app.executors.meta_optimization import MetaOptimizationTransport
from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.production_runtime import optimization_origin
from app.production_runtime.optimization_catalog import OwnedOptimizationCatalogHTTP
from app.production_runtime.optimization_catalog_contracts import OwnedOptimizationCatalogRead
from app.production_runtime.optimization_configuration import (
    OptimizationRuntimeConfigurationError,
    load_optimization_execution_configuration,
)
from app.production_runtime.optimization_contexts import (
    OwnedOptimizationContexts,
    owned_optimization_contexts,
)
from app.production_runtime.optimization_contracts import (
    OptimizationExecutionEvidence,
    OptimizationExecutionManifestV1,
    OwnedOptimizationInventoryRequestV1,
    RegisteredOptimizationEvidenceSource,
    admit_optimization_source,
)
from app.production_runtime.optimization_policy_contracts import OptimizationOperatingPolicyV1
from app.production_runtime.optimization_sources import registered_optimization_evidence
from app.production_runtime.optimization_transport import optimization_execution_transport
from app.publication.budget_period import financial_budget_period
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority
from app.publication.customer_optimization_contracts import (
    CustomerOptimizationRuntime,
    TargetCatalog,
    TargetRequest,
)
from app.publication.customer_runtime import utc_now
from app.publication.execution_contracts import (
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
    ProviderMandatePolicy,
)
from app.publication.execution_models import ProviderExecutionRevision
from app.publication.optimization_contracts import (
    MoneyContext,
    OptimizationIntent,
    OptimizationState,
    OptimizationTarget,
)
from app.publication.optimization_execution_contracts import (
    OptimizationQualification,
    OptimizationRuntime,
)
from app.publication.replacement_contracts import ReplacementEvidence, ReplacementSnapshot
from app.settings import Settings


@lru_cache(maxsize=4)
def pinned(
    path: str | None, digest: str | None, policy_path: str | None
) -> tuple[OptimizationExecutionManifestV1, OptimizationOperatingPolicyV1] | None:
    return load_optimization_execution_configuration(path, digest, policy_path)


def period(definition: GoalDefinition) -> tuple[datetime, datetime]:
    return financial_budget_period(definition)


class ConfiguredOptimization:
    def __init__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        configuration: Settings,
        manifest: OptimizationExecutionManifestV1,
        operating: OptimizationOperatingPolicyV1,
        stack: ExitStack,
    ) -> None:
        engine = db.get_bind()
        if not isinstance(engine, Engine):
            raise HTTPException(409, "optimization_engine_unavailable")
        self.sessions = sessionmaker(engine)
        self.principal, self.configuration = principal, configuration
        self.authorize = bind_authority(principal, provider)
        self.manifest, self.operating, self.stack = manifest, operating, stack
        self.clock = utc_now
        self.resources: (
            tuple[OwnedOptimizationContexts, OptimizationExecutionEvidence, httpx.BaseTransport]
            | None
        ) = None
        self.last_catalog: OwnedOptimizationCatalogRead | None = None

    def admitted_source(self, platform: str) -> RegisteredOptimizationEvidenceSource:
        source = admit_optimization_source(
            self.manifest,
            registered_optimization_evidence(self.manifest.evidence_source_id),
            platform,
        )
        if source is None:
            raise HTTPException(409, "optimization_source_unavailable")
        return source

    def resolve(
        self, scope: ExecutionAccount
    ) -> tuple[OwnedOptimizationContexts, OptimizationExecutionEvidence, httpx.BaseTransport]:
        registered = self.admitted_source(scope.account.platform)
        if self.resources is None:
            # Scenario real-transport rejection precedes both factory and credentials.
            transport = optimization_execution_transport(self.manifest)
            contexts = self.stack.enter_context(
                owned_optimization_contexts(
                    self.sessions,
                    self.authorize,
                    self.principal.user.id,
                    self.manifest,
                    self.configuration,
                    self.clock,
                    transport,
                )
            )
            evidence = registered.build(
                self.sessions, self.authorize, self.principal.user.id, self.clock
            )
            if evidence.descriptor != registered.descriptor:
                raise HTTPException(409, "optimization_source_changed")
            self.resources = (contexts, evidence, transport)
        return self.resources

    def origin_guard(
        self, db: Session, revision: ProviderExecutionRevision, policy: ProviderMandatePolicy
    ) -> None:
        document = optimization_origin.read(db, revision, policy)
        if (
            document is None
            or document.operating_policy != self.operating
            or document.evidence_profile_digest != self.manifest.evidence_profile_digest
        ):
            raise optimization_origin.unavailable()
        self.admitted_source(policy.accounts[0].account.platform)
        self.authorize(db, policy.workspace_id, self.principal.user.id)
        goal = goals.owned(db, policy.workspace_id, policy.goal_id)
        definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
        if (
            fingerprint(
                "inlet.optimization-goal.v1", {"definition": definition.model_dump(mode="json")}
            )
            != document.goal_digest
            or policy.total_cap_micros > definition.budget_micros
            or document.intent.aggressiveness != definition.aggressiveness
            or (policy.starts_at, policy.ends_at) != period(definition)
        ):
            raise optimization_origin.unavailable()

    def catalog(
        self,
        request: TargetRequest,
        now: datetime,
        original_mandate: ProviderMandateBinding | None = None,
    ) -> TargetCatalog:
        self.admitted_source(request.scope.account.platform)
        with self.sessions() as db:
            self.authorize(db, request.scope.workspace_id, self.principal.user.id)
            goal = goals.owned(db, request.scope.workspace_id, request.goal_id)
            goals.expect(goal, request.goal_revision)
            definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
            starts, ends = period(definition)
            if original_mandate is not None:
                from app.publication import execution_mandates

                _, original = execution_mandates.checked(
                    db,
                    request.scope.workspace_id,
                    original_mandate,
                    self.principal.user.id,
                    self.clock,
                )
                if (
                    original.goal_id,
                    original.goal_revision,
                    original.accounts,
                    original.currency,
                    original.time_zone,
                ) != (
                    request.goal_id,
                    request.goal_revision,
                    [request.scope],
                    definition.target_window.currency,
                    definition.target_window.time_zone,
                ):
                    raise optimization_origin.unavailable()
                starts, ends = original.starts_at, original.ends_at
        inventory = OwnedOptimizationInventoryRequestV1(
            request=request,
            money=MoneyContext(
                currency=definition.target_window.currency,
                currency_exponent=2,
                account_timezone=definition.target_window.time_zone,
                period_start=starts,
                period_end=ends,
            ),
            period_basis="original_mandate" if original_mandate else "confirmed_goal",
            original_mandate=original_mandate,
        )
        contexts, evidence, transport = self.resolve(request.scope)
        result = OwnedOptimizationCatalogHTTP(
            contexts.optimization,
            evidence.catalog_admission,
            environment=self.manifest.environment,
            transport=_BorrowedTransport(transport),
            clock=self.clock,
        ).read(inventory, now)
        self.last_catalog = result
        return result.catalog

    def runtime(self) -> CustomerOptimizationRuntime:
        google = (
            GoogleOptimizationTransport(transport=LazyTransport(self, "google_ads"))
            if "google_ads" in self.manifest.providers
            else None
        )
        meta = (
            MetaOptimizationTransport(transport=LazyTransport(self, "meta_ads"))
            if "meta_ads" in self.manifest.providers
            else None
        )

        def qualification(
            db: Session,
            binding: ProviderMandateBinding,
            scope: ExecutionAccount,
            target: OptimizationTarget,
            now: datetime,
        ) -> OptimizationQualification:
            result = self.resolve(scope)[1].qualification(db, binding, scope, target, now)
            revision = db.get(
                ProviderExecutionRevision,
                (binding.mandate_id, binding.revision),
                populate_existing=True,
            )
            if revision is None:
                raise optimization_origin.unavailable()
            policy = ProviderMandatePolicy.model_validate(revision.policy)
            document = optimization_origin.read(db, revision, policy)
            if document is None or (
                result.qualification_id,
                result.qualification_revision,
                result.evidence_digest,
            ) != (
                document.qualification_id,
                document.qualification_revision,
                document.qualification_digest,
            ):
                raise optimization_origin.unavailable()
            return result

        def exposure(
            db: Session,
            intent: OptimizationIntent,
            before: OptimizationState,
            qualification: OptimizationQualification,
            now: datetime,
        ) -> ExposureEvidence:
            return self.resolve(intent.scope)[1].exposure(db, intent, before, qualification, now)

        def replacement(
            db: Session,
            binding: ProviderMandateBinding,
            intent: OptimizationIntent,
            before: OptimizationState,
            qualification: OptimizationQualification,
            snapshot: ReplacementSnapshot,
            now: datetime,
        ) -> ReplacementEvidence:
            reader = self.resolve(intent.scope)[1].replacement
            if reader is None:
                raise HTTPException(409, "optimization_replacement_unavailable")
            return reader(db, binding, intent, before, qualification, snapshot, now)

        execution = OptimizationRuntime(
            environment=self.manifest.environment,
            qualification_reader=qualification,
            exposure_reader=exposure,
            context=lambda scope: self.resolve(scope)[0].optimization(scope),
            google=google,
            meta=meta,
            live_enabled=self.manifest.live_execution_enabled,
            authorize=self.authorize,
            mandate_origin_guard=self.origin_guard,
            replacement_reader=replacement if self.manifest.replacement_enabled else None,
        )
        from dataclasses import replace

        from app.planning_reporting.runtime import configured_bundle

        bundle = configured_bundle(self.sessions, self.configuration)
        planning = replace(bundle.initial, clock=self.clock) if bundle is not None else None
        return CustomerOptimizationRuntime(
            execution=execution,
            catalog=self.catalog,
            clock=self.clock,
            configured=self,
            initial_planning=planning,
        )


class LazyTransport(httpx.BaseTransport):
    def __init__(self, owner: ConfiguredOptimization, platform: str) -> None:
        self.owner, self.platform = owner, platform

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.owner.admitted_source(self.platform)
        if self.owner.resources is None:
            raise HTTPException(409, "optimization_context_required")
        return self.owner.resources[2].handle_request(request)


@contextmanager
def configured_optimization(
    db: Session, principal: CustomerPrincipal, provider: IdentityProvider, configuration: Settings
) -> Iterator[CustomerOptimizationRuntime | None]:
    try:
        config = pinned(
            configuration.optimization_execution_manifest_path,
            configuration.optimization_execution_manifest_digest,
            configuration.optimization_operating_policy_path,
        )
    except OptimizationRuntimeConfigurationError:
        raise HTTPException(409, "optimization_configuration_unavailable") from None
    if config is None or not any(
        admit_optimization_source(
            config[0], registered_optimization_evidence(config[0].evidence_source_id), platform
        )
        for platform in config[0].providers
    ):
        yield None
        return
    with ExitStack() as stack:
        yield ConfiguredOptimization(
            db, principal, provider, configuration, *config, stack
        ).runtime()
