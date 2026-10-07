# Production Execution Runtime Assembly: Next Package

Read-only engineering assessment of `4fadeda` (ordinary planning assembly inherited
from02377c8). This proposes full-product execution wiring, not a recommendation-only
release. No live evidence was collected, no settings enabled, and no database or
provider calls were made for this assessment. Launch scope remains Google, Meta,
TikTok and separately reviewed new campaigns/creative.

## Actual Unassembled Entrypoints

| Current factory | Consumer and missing assembly |
| --- | --- |
| [`get_customer_execution_runtime`](../../app/publication/customer_runtime.py) → None | [`customer_execution`](../../app/api/customer_execution.py) creation/catalog, exact approval, run/claim/dispatch, activation and original-attempt reconciliation. The facade requires concrete Google catalog/HTTP/context plus CreationRuntime and optional ActivationRuntime. |
| [`get_customer_optimization_runtime`](../../app/publication/customer_optimization_contracts.py) → None | [`customer_optimization`](../../app/api/customer_optimization.py), and execution facade optimization branches. Needs qualified target catalog, context, optimization readers/adapters and replacement reader. New read-only planning assembly does not supply these. |
| [`get_social_review_runtime`](../../app/publication/social_review_runtime.py) → None | [`customer_social_review`](../../app/api/customer_social_review.py) named social configuration, durable declarations and exact cover review; profiles/requirements/catalog are not installed. |
| [`get_creation_runtime`](../../app/publication/coordinator_contracts.py), [`get_activation_runtime`](../../app/publication/activation.py), [`get_optimization_runtime`](../../app/publication/optimization_execution_contracts.py), [`get_settlement_runtime`](../../app/publication/settlement.py) → None | Core ports are available, but the customer facade does not automatically discover them. No general creation/optimization dispatcher is wired into the customer worker simply by changing these getters. Settlement also lacks an authoritative final-cost source. |
| [`get_candidate_runtime`](../../app/optimization_candidates/service.py), [`get_candidate_selection_runtime`](../../app/optimization_candidates/selection.py), [`get_candidate_review_runtime`](../../app/optimization_candidates/review_bridge.py) → None | Owned candidate selection/review require exact registered policy, source-fence and current execution dependencies; no default source policy may be invented. |
| [`get_session_automation_runtime`](../../app/session_automation/runtime.py) → None | Both customer automatic-session API and [`session_automation.worker.run_due`](../../app/session_automation/worker.py), reached by [`run_customer_tick`](../../app/jobs/customer_runtime.py), need the same pinned policy/producer registry. Worker factory currently takes no engine argument; assembly must capture the actual caller engine, not import a global engine. |

The newly implemented budget consent endpoints intentionally close only conditional
local authority preparation. A consent or native v2 preview is not an executable
qualified target, exposure proof, or permission to publish creative.

## Existing Concrete Building Blocks And Remaining Seams

- Google/Meta/TikTok creation, optimization and activation HTTP adapters exist in
  `app/executors/{google,meta,tiktok}_{publication,optimization,activation}.py`.
  Their real serializers/readbacks and unknown-state behavior are usable. Runtime
  assembly must not add automatic retries or treat an absent/old value as no effect.
- [`GoogleCatalogHTTP`](../../app/collectors/google_catalog.py),
  [`qualify_google`](../../app/publication/google_qualification.py) and canonical
  Google compilers provide actual bounded native configuration reads. This proves
  configuration facts only; it does not prove portfolio financial bounds.
- [`MetaCatalogHTTP`](../../app/collectors/meta_catalog.py) and
  [`SocialPlanProducer`](../../app/publication/social_customer_producer.py)
  provide social configuration/plan machinery with persistent declaration/cover
  bindings. Native TikTok catalog parsing remains explicitly unverified; retained
  [response evidence](tiktok-catalog-response-evidence.md) specifies the missing
  native response fixtures. Do not install the decoded fixture reader as a live
  native parser or clear its blocker.
- [`ConfiguredOptimizationCatalog`](../../app/publication/customer_optimization_catalog.py)
  currently takes operator-enumerated NamedOptimizationTarget objects including
  MoneyContext, qualification ID/revision. It is not automatic discovery. Native
  inventory/MetaBudgetHTTP observations cannot be cast into those qualified records.
  Period, actual budget owner/shared scope and independently admitted qualification
  must come from the current owned mandate and approved provider profile, not a UUID
  or a customer-supplied money/proof object.
- [`owned_meta_budget_reader`](../../app/collectors/owned_meta_budget.py) and
  [`NativeDiagnosticService`](../../app/collectors/native_diagnostics.py) demonstrate
  actual per-request vault, source generation and original-authorizer context reads.
  These patterns can be factored into execution-owned context factories, preserving
  credential refresh generation fencing and short private sessions. Credentials
  remain ephemeral; contexts must be rechecked immediately around actual IO.

### Financial And Accounting Ports Must Remain Separate

[`CreationRuntime`](../../app/publication/coordinator_contracts.py) needs a
ConfigurationQualification reader and ExposureReader. Configuration qualification
must bind exact plan/API version/current source and expire promptly; adapter local
schema validation is not provider acceptance. Live unsupported field combinations
remain unresolved even if MockHTTP accepts them.

[`PortfolioExposureReader`](../../app/publication/exposure_qualification.py) composes
server PortfolioFacts and qualification profiles with current shared ledger/holds.
It has **no default live source**. Required facts cover every exact consented account,
period/currency, reporting watermark, reported spend, unreported upper bound,
unchanged future upper bound and proposed owner's upper bound. A missing bound is
unknown, never zero. Profile/fact/policy freshness and minimum expiry remain bound.
For activation, use its `for_activation` exact retained-reservation path, excluding
only that original hold once; preserve all other holds and original lineage.

Optimization's QualificationReader and ExposureReader have different signatures;
they require actual target current state, exact mandate and qualification.
ReplacementReader additionally binds the immutable predecessor snapshot and closed
original request accounting. Do not reuse the creation facts reader by ignoring
these arguments. `replacement.transfer` owns atomic accounting; neither reductions,
pauses nor provider success alone release reserved exposure. SettlementReader must
prove its existing settlement contract; if proof is unavailable, retain the hold.

Restricted-profile proposals for [Google](google-restricted-mandate-profiles.md) and
[Meta/TikTok](meta-tiktok-restricted-operating-profiles.md) distinguish enforceable
Inlet-authored request restrictions from conditional provider caps and guarantees
against outside writers. They are engineering proposals, not installed or
empirically qualified profiles. Assembly must not silently resolve that distinction
by changing the current financial gate.

## Proposed Shared Assembly Interface

New files (names proposed, no shared code changed here):

- `app/production_runtime/contracts.py`: frozen versioned ProductionRuntimeManifestV1.
  Required environment, manifest identity/revision, exact profile registry digests,
  provider-specific supported configuration profile references, explicit capability
  selections and all request/page/response/deadline/freshness limits. No credentials,
  proof JSON, guessed qualification ID or numeric defaults. Separate capability
  installation from live execution admission; absent exact evidence is unavailable.
- `configuration.py`: bounded file + canonical digest loader; separate pin from
  planning/reporting and budget consent. Keep all existing serialized hashes intact.
- `owned_contexts.py`: actual scope/generation/vault refresh factories using supplied
  session factory, with no global actor/principal or sockets on construction.
- `assembly.py`: construct/dispose concrete adapters and named catalogs, wire existing
  coordinator ports and original-session authorizers; return explicit unavailable
  reasons for unsupported/missing providers instead of manufacturing a runtime.
- `qualification_sources.py`: registry of concrete server configuration/evidence
  readers. Live registry entries require their actual implementation/profile match;
  strings in a manifest cannot create qualified facts. Test scenario source is
  explicitly contract_test only and impossible to select in a live manifest.

Proposed callable signatures:

```
load_production_manifest(path, expected_digest) -> ProductionRuntimeManifestV1 | None
build_execution_bundle(
    sessions: Callable[[], Session], settings: Settings,
    manifest: ProductionRuntimeManifestV1, sources: ProductionEvidenceSources,
    clock: Callable[[], datetime]
) -> ContextManager[ExecutionBundle]
ExecutionBundle.customer_execution(principal, identity_provider) -> CustomerExecutionRuntime | None
ExecutionBundle.customer_optimization(principal, identity_provider) -> CustomerOptimizationRuntime | None
ExecutionBundle.social_review(principal, identity_provider) -> SocialReviewRuntime | None
ExecutionBundle.session_automation() -> SessionAutomationRuntime | None
```

`ProductionEvidenceSources` is trusted server code, not a request/settings dictionary:
separate creation configuration/exposure, activation exposure, optimization
qualification/exposure, replacement, settlement and candidate source/epoch producer
ports retain their existing exact signatures. It must report capability absence
without invoking provider IO. The registry's default missing-live-source behavior
remains deny; installing a manifest is not authorizing proof.

Customer dependencies build from `db.get_bind()` plus the request's original
principal/provider, retain adapter lifetime through request completion, and bind
`bind_authority` at every coordinator boundary. Worker entrypoint builds with its
actual engine and the same frozen manifest/source registry, then reconstructs each
stored original session through existing automatic-session guards. Never cache a
principal or elevate a closed automatic session to an operator service account.
Existing synchronous customer dispatch remains explicit; no new general dispatch
queue or implicit activation is introduced in this first assembly package.

API and worker process pinning requires coherent deployment/restart. This does not
provide global hot reload or revocation. Local revoke, exact current source/session
checks and existing kill switches retain their current behavior.

## Next Bounded Implementation Slice

Start with **actual owned execution context/catalog assembly and ordinary Google
creation + separately approved activation entrypoints**, using existing concrete
HTTP adapters, current approved creative/media and exact production mandate. Google
is the first implementation slice, not the launch scope limit. Freeze the manifest,
context/reader registry and capability classification before parallel Meta/TikTok
assembly. Keep live capability unavailable wherever real exposure/configuration
qualification is missing; this work must still run the entire durable execution
journey in contract_test, not merely return a constructed dataclass.

Follow with Meta actual context/catalog/declaration assembly; TikTok native catalog
parser after authoritative response shapes; existing-campaign qualified target
producer + optimization/replacement; settlement source; finally candidate/automatic
session worker assembly against those exact ports. These dependencies are concrete
code/data gaps. They should remain tracked until the full MVP works.

Acceptance for the first slice:

1. Start ordinary configured API with actual engine, owner session, approved B14
   creative/media and separately consented mandate. No runtime dependency overrides
   or seeded execution review/attempt/hold/receipt. Fixture supplies explicit server
   manifest and contract_test evidence scenario through the private server registry;
   do not call this live financial qualification.
2. Inject HTTP at the lowest transport seam, including actual OAuth/context/catalog
   reads. Drive catalog → canonical plan/configuration reads → exact review/approval
   → durable reservation/claim → concrete paused graph requests → scoped readback.
   Actual API supplies no receipt, exposure proof, raw resource JSON or qualification.
3. Separately review/approve activation, preserve the exact original hold, dispatch
   status-only requests with complete graph checks, and read actual receipt. Timeout
   preserves original attempt/fence/hold; retry only reconciles that original request.
4. Verify cancellation, revocation, generation/media/config drift, policy expiry,
   wrong account/tenant, post-claim race and incomplete/unknown facts all deny without
   new writes or lost holds. Live + scenario source must reject before provider IO.
5. Assert constructor/default-disabled paths open no sockets; run real TLS customer
   journey on SQLite/PostgreSQL. When automatic wiring is reached, test the shipped
   run_customer_tick entrypoint with original-session revocation and bounded due
   admission, not only a direct coordinator call.

## Required Inputs Versus Ordinary Engineering

Ordinary code work: engine-bound context factories and refresh fencing, loader and
capability assembly, native catalog producers, fresh evidence acquisition/cache
binding, concrete entrypoint journeys and failure tests. No further owner policy
decision is required to implement those missing mechanics safely offline.

Owner/operator qualification inputs: explicit supported provider operating profiles,
actual monetary exposure semantics and evidence provenance, policy thresholds and
freshness/cadence values, eligibility/permissions and deployment capability switches.
Provider response schema evidence is required for TikTok catalog decoding. Real
credentials, customer ad mutations and empirical live validation require separately
authorized setup; none should be fabricated to turn a capability green.

The next package must not claim full live execution completion merely because a
contract_test source makes the ordinary configured journey work. Conversely, missing
live evidence is not a reason to stop implementing the actual full-scope machinery.
