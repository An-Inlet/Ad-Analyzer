# Configured Existing-Campaign Optimization Runtime

Design-only child of Meta/Google composition `55e6a35`. Existing-campaign optimization
is core Inlet scope. This proposal supplies ordinary customer execution wiring, not
recommendation-only behavior or an alternative to the approved spending mandate.
No live source, new migration, model call or provider action is proposed here.

## Concrete Existing Pieces And Missing Connections

- `customer_optimization_contracts.get_customer_optimization_runtime()` and
  `optimization_execution_contracts.get_optimization_runtime()` return None.
  `app/api/customer_optimization.py` and generic customer execution run/review routes
  therefore have no ordinary configured optimization runtime.
- `OptimizationRuntime` already accepts qualification/exposure/context, actual
  Google/Meta/TikTok transports, optional replacement reader and explicit candidate/
  automatic/initial-preview guards. Keep these ports and their accounting semantics.
- `GoogleOptimizationTransport` and `MetaOptimizationTransport` already implement
  exact current read, budget/pause updates, readback and uncertainty reconciliation.
  They accept an independently supplied qualification identity and MoneyContext.
  They do not discover or qualify those values. Target-state observation is not CAS,
  delivery timing, request termination or settled spend.
- `ConfiguredOptimizationCatalog` requires a static tuple of NamedOptimizationTarget
  objects with manually supplied qualification IDs/money. It is an explicit injected
  fixture/operator seam, not actual ordinary native discovery. Do not install it with
  random IDs, fixed native IDs or invented account/period values.
- `customer_optimization.discover` already refreshes original session, current
  confirmed goal and owned generation before/after catalog IO. TargetOption opaque
  IDs commit the request and complete qualified state. Keep that public contract.
- `GoogleNativeInventoryHTTP` supplies actual bounded account/campaign/budget/billing
  observations and explicitly unqualified spend fields. `MetaBudgetHTTP`
  (in `collectors/meta_budget.py`) supplies GET-only campaign observations through
  `meta.budget_snapshot.parse_meta_budget`; initial-planning v2 accepts these only
  as read evidence. Neither is a source of OptimizationQualification.
- `prepare_optimization` already obtains current mandate qualification, commits the
  read phase, reads actual native state, obtains exposure, and rechecks the exact
  mandate/ledger before review persistence. Repeat review uses ReplacementReader;
  settlement uses SettlementReader with all-original-attempt terminal proof.

## First Bounded Supported Inventory

Offer existing campaigns only for this assembly slice: Google v25 and Meta v26.
Keep actual adapters' unsupported feature checks; do not add new adset/campaign
formats or shared-budget support just because an inventory row exists. Budget and
pause are existing exact actions; no resume, new creative or campaign publication.
Each option must resolve an entire actual budget owner and complete affected target
set, with supported currency, native timezone, schedule and explicit operating rules.

Google: reuse the current account inventory collector, its real campaign/budget
resource joins and completeness flags. A fixed-window reporting query must derive
from the confirmed goal/mandate period and account timezone, never fabricate a
financial period to obtain inventory. Unqualified numeric inventory fields remain
unqualified. Reject missing/shared/ambiguous owners where the adapter cannot prove
complete affected scope; no limited first-page list may be labeled complete.

Meta: use the existing account-scoped campaign listing wire/parser and bounded
pagination as candidate discovery, then the actual optimization current-state
adapter for each separately admitted candidate. Existing imported campaign labels
may assist presentation but do not prove current native existence, ownership,
generation or full topology. Preserve status/owner fields and the existing complete
campaign/adset topology parser; missing/deleted/inaccessible targets cannot become
zero-budget options. Reuse the existing budget snapshot parser where applicable;
never cast NativeBudgetObservationV1 or InitialPreviewV2 into OptimizationState.

Cap inventory at50 offered campaign candidates and existing collector byte/page/
request/deadline bounds. Fail unavailable on truncation or incomplete inventory,
not a partial catalog claiming complete. A complete inventory may omit explicitly
unsupported/unqualified candidates; return fixed exclusion reason counts in a
separate sanitized discovery projection if needed, without minting TargetOptions.
No background discovery queue or automatic replay is required for this package.

## Minimal New Interfaces Before Implementation

Add `production_runtime/optimization_contracts.py` with:

```
OptimizationExecutionManifestV1:
  schema_version, manifest_id, revision
  environment: contract_test | live
  providers: nonempty unique subset [google_ads, meta_ads]
  evidence_source_id, evidence_profile_digest
  operating_policy_digest
  live_execution_enabled: required bool
  replacement_enabled: required bool
  settlement_enabled: required bool
  credential_minimum_remaining_seconds: required bounded int
  context_lifetime_seconds: required bounded int

OwnedOptimizationInventoryRequestV1:
  request: existing TargetRequest
  money: existing MoneyContext
  # Exact confirmed goal period for first discovery; original mandate period for
  # current-policy rediscovery. Canonical timezone boundary helper, no default horizon.

OwnedOptimizationCandidateV1:
  request_digest, label, parent_label, target: OptimizationTarget
  inventory_digest, observed_at, expires_at
  # Candidate names/identity only; no qualification/exposure/permission claim.

OptimizationCatalogAdmissionReader:
  (request: OwnedOptimizationInventoryRequestV1,
   candidate: OwnedOptimizationCandidateV1, now)
    -> OptimizationQualification | None

OptimizationExecutionEvidence (server-only dataclass):
  descriptor: source ID/profile/environment/kind
  catalog_admission: OptimizationCatalogAdmissionReader
  qualification: existing OptimizationQualificationReader
  exposure: existing OptimizationExposureReader
  replacement: existing ReplacementReader | None
  settlement: existing SettlementReader | None

RegisteredOptimizationEvidenceSource:
  descriptor
  build(sessions, authorize, actor_id, clock) -> OptimizationExecutionEvidence

configured_customer_optimization(db, principal, provider, settings)
  -> request-owned context manager[CustomerOptimizationRuntime | None]
```

Admission is a trusted source implementation, not a JSON qualification template.
It must establish stable exact qualification identity/revision and a current bound
money horizon for that owned target. The subsequent actual adapter read uses that
identity, and must match admitted account/currency/timezone/owner scope; downstream
exposure still verifies the complete budget owner and affected targets. No admission
means no eligible option. A valid source may return None; absence is not a dummy
qualification ID or an empty proof upgraded to complete.

The normal post-consent qualification reader independently revalidates the same
current source qualification lineage under the exact mandate binding. It must not
reuse a discovery result just because its option ID is still visible. A change in
qualification revision, native state or goal produces a fresh opaque option and
requires review again. Existing plan/receipt schemas remain unchanged.

Inventory is concrete first-party HTTP implemented in this package, not another
configurable inventory callback. Only empirical/native qualification and economic
facts use trusted admitted source ports. The source implementation can perform its
own bounded authoritative reads; its descriptor is identity, not evidence. Fixture
sources explicitly say contract_test and supply test-qualified facts while real
HTTP adapters are exercised through MockTransport. Shipped real transports reject
contract_test before construction. No default live source or import-string registry.

## Financial And Customer Policy Boundaries

Catalog bootstrap precedes a new mandate: derive the exact MoneyContext from the
current confirmed goal's currency, timezone and budget period using strict local
boundary conversion. After consent, use the original immutable ledger/mandate
period and currency, even when a newer goal suggests different dates. Never open a
new ledger to bypass held exposure, unknown attempts, existing account-set locks or
spent high-water. Discovery cannot free, resize or create reservations.

The existing OptimizationPolicyIntent exposes technical limits and `make_policy`
currently hardcodes freshness60. Do not promote those into the new simple customer
flow. Use a separately pinned explicit server operating policy with the approved
named-aggressiveness mapping and caps/action limit/cooldown/freshness. Reuse
BudgetMandateRuleV1 semantics without silently changing its existing profile binding
or v1 digest. Customer confirms meaningful amount/scope/aggression, never supplies
proof or is forced to choose technical freshness/cooldown limits. Overall total
cannot exceed the confirmed goal budget; 5/10/20 are policy inputs, not authority to
increase that total. Missing server operating policy disables consent honestly.

Before code freeze, choose an additive optimization-specific intent/provenance
adapter over existing immutable authority records. If current0079 provenance cannot
honestly bind this different discovery/profile lineage, report the exact minimal
schema delta for review instead of writing a new migration silently. Do not overwrite
or reinterpret existing policy/consent records or NativeV2 review handoff.

Repeat capability is available only with an admitted actual ReplacementReader and
unchanged coordinator replacement snapshot checks. Settlement capability requires
its admitted reader and real terminal/reporting proof; missing reader means holds
remain held. Paused/absent/current-old-value state never proves termination, zero
remaining cost or authority to replay. Keep original attempt/resource lineage and
same portfolio ledger across initial optimization, repeat and settlement.

## Request Assembly And Forward Gates

Reuse55's owned vault access, actual request engine, original-session authorizer,
short private sessions and ExitStack cleanup. Add optimization context conversion
from exact ExecutionAccount; never fabricate PublicationScope/mandate IDs merely
to call a publication context. Required provider credentials remain private.

Google/Meta optimization manifests must agree with any composed execution environment
when a shared request uses both. Missing optimization configuration must leave
creation/activation and planning/reporting available. Provider dispatch uses typed
scope/original request; TikTok denies before factory/credential/HTTP construction.
Legacy explicitly injected tests remain supported. No URL-only dispatch.

New configured dependency replaces the ordinary optimization getter seam and feeds
existing generic review/run/reconcile APIs. Settlement assembly uses its existing
separate getter/dependency, only when enabled and its source port exists. Bind all
runtime authorizers to the original session; refresh goal/source/generation/policy
around IO and again under existing final locks. Keep existing candidate/automatic/
initial-preview bridge guards explicit; do not install permissive callbacks. Native
preview v2 remains a non-authorizing observation until a separately qualified exact
optimization selection has completed the existing review process.

## Concrete Acceptance After Interface Approval

Both DBs, actual ordinary configured APIs and TLS page; no runtime-getter overrides,
seeded optimization review/attempt/receipt/hold or browser-native-ID/proof input:

1. Current owned Google/Meta connection and native MockHTTP campaign inventory;
   discover real labels and opaque targets, including pagination/completeness and
   unsupported/missing/foreign candidate handling. Actual state read follows genuine
   server admission; unqualified native-only evidence cannot produce a target option.
2. Goal budget/named aggression → server-derived bounded mandate review/consent →
   exact budget or pause review → approval → actual mutation/readback. Persist one
   original attempt/receipt and conservative held exposure under the same ledger.
3. Repeat the same budget owner only through admitted replacement evidence; source,
   previous receipt and hold changes invalidate the prepared review. Unknown update
   retains its fence/hold and reconciles original intent without resending.
4. Separate settlement success only for explicit terminal-complete scenario evidence;
   missing/late/unclosed-original facts keep holds. No recycling on pause or absence.
5. Original-session revocation, generation/account/goal/policy drift during HTTP,
   currency/period mismatch, full target-set change and stale qualification deny.
   Real transport+scenario source and direct/stored TikTok operations deny before IO.
6. Google/Meta creation/activation TLS, existing v1 hashes and NativeV2 informational
   preview/review-rejection regressions remain intact.

Owner/evidence inputs are explicit operating policy, exact supported provider
qualification profiles, and empirical bounded exposure/replacement/settlement
sources. Offline wiring, strict collectors, named customer selection and real API/
TLS proof are implementable engineering now and must not wait for invented inputs.
No source ID, native cap or owner approval alone provides universal external-writer
control or proves unreported/future cost.

TikTok remains blocked as recorded in
[tiktok-catalog-response-evidence.md](tiktok-catalog-response-evidence.md): exact
versioned collection/element/nullability/ownership/status/event and pagination
response tables plus sanitized valid/multipage/empty/inaccessible/error fixtures
are missing. That identity/pixel evidence gap must not be guessed or endlessly
researched again. Existing-campaign inventory would additionally require its own
exact campaign/adgroup response completeness/owner schemas before offering named
options; existing typed mutation adapters do not supply discovery qualification.

## First Contract Freeze And Origin Proposal

New additive modules `production_runtime/optimization_contracts.py` and
`optimization_policy_contracts.py` define the manifest, scoped inventory/admission,
trusted evidence/context ports and separate explicit operating-policy/customer
intent models. No getters, factories, database schema or existing v1 models changed.

The concrete immutable origin and anti-bypass plan is in
[optimization-mandate-provenance-schema.md](optimization-mandate-provenance-schema.md).
It proposes a dedicated sidecar plus immutable revision origin discriminator and
preparation digest, with a deferred owned FK requiring atomic sidecar insertion.
Generic consent/forward gates must require provenance for marked revisions;
configured optimization must not fall back through the legacy technical-knob route.
Existing legacy authority remains readable/reconcilable without reclassification.
Migration implementation and number remain pending root review.
