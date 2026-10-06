# B17 Action Outcome Evidence Proposal

Status: design only, 2026-10-06. No schema, migrations, executor changes, schedules,
provider requests, or spending authority are introduced. Reviewed foundation commit
`73725be8c3ce8165d236f998cc850b41cea1f10c` is the stable code baseline. Social contracts
are inspected separately at `0d14edc` in `inlet-social-adapters`; they are a dependent
proposal, not an assertion that production orchestration is installed.

## Recommended Boundary

Produce an immutable, content-addressed **observational evidence document** for one
exact action and a predefined pair of measurement windows. An effect receipt means
an operation was observed at a provider; it does not mean sales increased because
of that operation. Keep execution status, measurement completeness, comparability,
and causal interpretation separate. Report “observed before/after difference” only
when the metric-specific comparability gate passes. Never report causal lift,
incrementality, guaranteed ROI, or permission to expand a spending mandate.

Begin with a pure evaluator of frozen, already-authorized inputs. Do not create a
background enrollment/collection job until the scheduler-owned production receipt
port and historical measurement lineage are available. Fixture evaluations remain
explicitly synthetic. A new paused/disabled campaign has no established pre-action
campaign history or confirmed activation: show its deployment evidence and
insufficient performance comparison, not a manufactured zero baseline.

## Existing Code And What It Proves

| Existing source | Concrete fields or semantics | Limits for B17 |
| --- | --- | --- |
| `app/mandates/schemas.py: AccountScope, ActionDraft` | Account ID, connection ID, platform; action kind/resource key/payload digest/expected-state digest/exposure/positive-change bound/mandate revision | These are simulation contracts. They are not a production receipt and do not bind a connection generation or confirmed effect time. |
| `MandateDefinition` and `spending_mandate_revisions` | Goal ID/revision, currency/time zone, fixed period, account scopes, caps; revisioned definition and approval | Join the exact historical revision, never the latest mutable mandate. Goal association is indirect through the mandate revision. |
| `MandateAction` | Workspace, mandate, draft and digest, reviewed/claimed/dispatched times, fence, state, settled amount | Mutable state and settlement are not a complete immutable production evidence feed. Simulation settlement is not actual advertising spend. |
| `app/publication/contracts.py: PublicationScope` | Workspace, `AccountScope`, external advertiser ID, connection version, mandate ID/revision | Reuse exact scope. Connection version is a string; do not infer a generation from an undocumented encoding. |
| Fixture `BoundRequest` / `PublishReceipt` | Exact request digest, plan/step/fence, dispatch/observation timestamps, outcomes `verified_effect`, `verified_no_effect`, `unknown`, `conflict`; verified resources are PAUSED | Explicit offline fixture only; no real performance evidence or activation proof. |
| Google `BoundProviderRequest` / `ProviderReceipt` | Plan/review/request digests, scope, step operation, fence, dispatched_at; same outcome enum, resource_name, readback_digest, evidence enum, observed_at | Acknowledged response is not verified effect. `observed_at` is readback time, not the exact effective timestamp. Current provider plan is ineligible for publication. |
| Meta/TikTok `SocialBoundRequest` / `SocialProviderReceipt` | Same binding plus API versions v26.0/v1.3, resource_kind, provider-qualified resource_name | Inspected on dependent social branch; production durable receipt integration remains scheduler-owned. |
| `publication_plans`, `publication_steps`, `publication_receipts` | Scoped action linkage, document/digest, step request/receipt; immutable-style receipt rows with request/receipt JSON, digest, recorded_at | Stable coordinator presently accepts fixture documents. Do not silently parse arbitrary JSON as qualified production evidence. |
| `app/executors/google_actions.py: GoogleState, GoogleChange` | State fingerprint, observed_at, campaign/budget/customer IDs, status, budget, negative keywords; typed change | Fixture-only action execution. A separate adapter is needed to normalize existing-campaign outcomes into the production evidence port. |
| `app/commerce/reporting.py: measurement(..., snapshot=True)` | Shopify definition, store, currency/time_zone, half-open window, as_of, watermark, store revision, quality/reasons, net sales/orders/customer coverage, snapshot_id | Canonical merchandise sales, not ad-attributed sales. No action/account attribution is implied. Completeness is not finality after refunds/corrections. |
| `CommerceSnapshot`, `CommerceDailyRevision` | Frozen result and store revision; revisioned daily aggregate values/as_of | Snapshot identity lacks a digest; store revision is a data revision, not a provider grant generation. Privacy/retention paths intentionally delete snapshots. |
| `GoalRevision`, `GoalPreview` | Frozen goal definition, confirmation timestamps; preview references a commerce snapshot | Confirmed baseline may later be erased or corrected. Do not replace it silently with the latest goal or snapshot. |
| `MeasurementContractSnapshot`, `UnifiedOutcomeSnapshot` | Contract version/source-of-truth/attribution/lookbacks/maturity/value horizon; cohort range, mature_through, as_of, currency, coverage, readiness, campaign/ad-group totals | Repository reads current ORM contract/mappings; no persisted immutable report lineage or source-generation manifest. Unified cohorts use UTC day boundaries and inclusive end dates, unlike store-local half-open commerce windows. |
| `DailyMetric`, account/connection models | Scoped campaign hierarchy and daily metrics; accounts have currency/time_zone; Google/Meta/Source connections have generation | Mutable daily facts do not carry a complete publication-batch/generation/definition/watermark snapshot for each metric day. Row presence alone does not prove complete source coverage. |

Relevant implementation details: `UnifiedOutcomeService` computes maturity from
`as_of.date() - outcome_maturity_days`, clips `mature_through` to the requested
inclusive cohort end, and rejects unsupported engaged-view attribution. The current
commerce definition is `shopify_merchandise_net_sales_v1`: merchandise after
discounts/refunds, excluding tax/shipping, with refunds on processing date. B17
must preserve these semantics and cannot relabel them “ad revenue.”

## Proposed Document, Not A New Executor Interface

Name: `inlet.action-outcome-evidence.v1`. Canonical JSON with sorted object keys,
explicit nulls, sorted unordered reason/reference sets, integer micros, finite
Decimal strings, ISO UTC instants and IANA zone names. Hash with domain separation
using the existing publication `fingerprint` pattern. Exclude the document's own
hash from its hash input. Equal inputs and evaluator version produce equal hashes;
created-at/ID metadata may live outside the deterministic content.

1. **Identity and provenance**: schema/evaluator/policy version; workspace ID;
   evidence mode (`synthetic` or `observed_provider_readback`); subject action ID
   and digest; operation kind; exact plan/review/step/request/receipt digests and
   IDs; source snapshot references and digests; `as_of`; optional `supersedes`.
   Do not include tokens, raw requests/responses, customer identifiers, creative
   text, contact fields, URLs containing secrets, or CRM profile payloads.
2. **Scope**: immutable advertising account tuple (workspace/platform/connection/
   internal account/external advertiser), canonical entity kind and owned entity
   references; connection version and separately proved generation; mandate
   ID/revision/definition digest; goal ID/revision/definition digest and confirmed
   baseline reference. Commerce is a second explicit source scope (workspace,
   store, integration, store data revision, proved source identity), never inferred
   to equal the advertising account. Missing generation remains missing.
3. **Execution evidence**: authoritative receipt reference; mode; exact provider
   outcome and evidence type; dispatch and observed timestamps; effective-time
   interval or null; activation/delivery proof separately from resource creation;
   before/after state digests where available; reconciliation/supersession chain.
   A confirmed readback can bound an effect between dispatch and observation when
   the transport guarantees that relationship, but does not establish an exact
   instant. Unknown/conflict/no-effect are retained without synthesizing success.
4. **Comparison specification**: chosen before/after windows, exclusion/washout
   interval, calendar basis, zone, UTC interval boundaries, duration/day counts,
   selection policy/version and reason. Freeze this before evaluation; do not
   search windows for a favorable result. Disallow overlap and action-containing
   “before” windows. Post window begins after the verified effect upper bound and
   any policy-defined exclusion. No default washout or maturity days are invented.
5. **Measurement basis per metric**: source-of-truth; metric definition ID/version
   and transformation version; grain; currency/unit; time zone and aggregation
   basis; attribution model and exact click/view lookbacks or explicit
   `not_applicable_store_total`; maturity/value-horizon policy; selected conversion
   action/event mapping digest; canonical owned entity mapping. Shopify sales,
   platform conversion value, and unified CRM business revenue are different
   series and must never be summed as one revenue metric.
6. **Frozen window observations**: start-inclusive/end-exclusive local and UTC
   bounds; raw source range semantics; `as_of`; source watermark and data revision;
   immutable snapshot digest; value or null; numerator/denominator where relevant;
   complete/missing/explicit-zero days; expected/observed entity coverage;
   attribution matched/unmatched counts; currency mismatch counts; source quality
   and readiness reasons; `mature_through` and required mature-through boundary.
7. **Corrections and confounders**: previous evidence/snapshot refs; changed source
   revision/definition/generation flags; late conversions/refunds/reconciliations;
   privacy invalidation; overlapping action/change refs; scope/currency/zone
   changes; tracking changes; available inventory/pricing/promotion/site signals;
   each marked observed, user-reported, or unknown. Absence of a monitored change
   is not proof that no confounder exists. No inferred sensitive attributes.
8. **Evaluation**: execution eligibility; metric-level comparability status;
   explicit insufficient reasons; before/after observed values, absolute delta,
   relative change only when the baseline is valid and nonzero; coverage warning
   set; `interpretation = observational_only`; `causal_lift = null`;
   `spending_authority = none`. A zero or negative baseline yields no percentage
   change; zero is not missing, and missing is never coerced to zero.

Use a frozen strict model eventually, and canonical serialized copies of nested
inputs: existing `StrictModel` rejects extra fields but is not immutable. Merely
wrapping mutable ORM models or a mutable dict in a frozen dataclass is insufficient.

## Comparability And Maturity Rules

Evaluate independently for each metric and requested scope. A business-metric
failure need not erase an independently valid advertising-cost observation, but
there is no overall “improved” badge if the goal metric is insufficient.

Required equality: owner/source identity, account/entity scope, generation or an
explicitly qualified continuity proof, metric definition, currency, zone, time
basis, attribution/mapping version, and aggregation grain. Do not apply implicit
FX conversion or interpret different attribution windows as equal. Goal/mandate
revision changes create a new evaluation lineage, not an update to the prior claim.

The requested windows must be fully available, equally mature under the frozen
policy, and comparable by the declared calendar policy. For cumulative windows,
require equal local-day duration; for calendar-month comparisons preserve exact
calendar months and disclose unequal day counts. Do not silently transform a
monthly goal to a 30-day goal. Daylight-saving changes require local/UTC boundaries
and local-day versus elapsed-hour durations to remain explicit.

A clipped unified `mature_through` is insufficient for the full requested window;
never compare the full before window with a silently shortened after window.
Require watermark freshness and complete expected coverage for both windows.
A successful last sync, metric row count, or “no records” response alone is not
proof of complete zero activity. Explicit completed-window coverage must distinguish
zero activity from missing pages/partial imports and the absence of a campaign.

Shopify complete windows may still change when refunds occur or history is
reconciled. Mark them observed-as-of, not final. Do not borrow the CRM contract's
maturity days for Shopify refund finality. Until a commerce maturity policy exists,
store-total observations may be displayed as provisional context; they do not
satisfy a “mature action outcome” qualification by themselves.

Do not use a new campaign's nonexistent before history as zeros. A comparison at
account/store level is a separately specified context series with other activity
and confounders, not a surrogate estimate of that campaign's incremental impact.

Suggested bounded reason taxonomy:
`synthetic_only`, `receipt_unavailable`, `effect_unverified`, `effect_conflict`,
`verified_no_effect`, `activation_unverified`, `effective_time_unknown`,
`goal_revision_unavailable`, `mandate_revision_unavailable`, `scope_mismatch`,
`generation_unknown`, `generation_changed`, `entity_mapping_unavailable`,
`measurement_contract_unavailable`, `metric_definition_changed`,
`attribution_changed`, `currency_mismatch`, `timezone_mismatch`,
`window_not_comparable`, `window_not_closed`, `window_not_mature`,
`maturity_policy_unavailable`, `missing_coverage`, `stale_source`,
`import_in_progress`, `source_error`, `unreconciled_source`,
`privacy_suppressed_source`, `outside_retention`, `snapshot_unavailable`,
`source_correction_pending`, `baseline_missing`, `baseline_zero`,
`overlapping_actions`, `confounder_coverage_unknown`.
Preserve source-specific reason codes as nested provenance; map to stable display
labels. Some codes are warnings or calculation-specific blocks rather than a
universal rejection (e.g. baseline_zero blocks relative change, not absolute delta).

## Missing Ports And Ownership

| Needed boundary | Recommended owner and requirement |
| --- | --- |
| Qualified immutable action receipt read port | Scheduler/production-receipt owner. Typed normalized projection, exact scopes/digests, mode, confirmed/unknown/no-effect/conflict, observation time, predecessor receipt chain; keep acknowledged responses separate. B17 reads only. |
| Production existing-campaign action normalization | Same owner plus provider adapters. Current Google fixture operation state is not a substitute for this port. Meta/TikTok publication typed results alone do not cover budget/pause/resume operations. |
| Activation/effective-time evidence | Publication owner. Creation of paused/disabled assets is insufficient. Receipt must explicitly distinguish deployment, activation, delivery and their known time bounds. No B17 activation code. |
| Historical source snapshot manifest | Measurement/collector owners. Scope/generation, completed-window/page lineage, zero coverage, currency/zone/conversion definition, correction revision, watermark, source-specific maturity. Digest normalized aggregates rather than raw customer events. |
| Immutable measurement contract and report export | Measurement owner. Current contract plus mappings need a frozen versioned content digest; report dataclasses are not durable snapshots. UTC inclusive cohorts require explicit half-open export mapping. |
| Canonical campaign/entity resolution | Collector owners. Provider resource names must resolve to an owned canonical entity at the receipt generation; reject ambiguous/foreign IDs and do not join on provider ID alone. |
| Commerce revision and privacy invalidation | Commerce owner. Reuse snapshot/revision/quality semantics; source revisions are not grant generations. Existing disconnect/erasure/retention deletes snapshots and must invalidate dependent B17 evidence/values. |
| Confounder observation | Read-only action history plus explicit known signals; absence remains unknown. No newly authorized CRM retention or live telemetry collection. |

B17 must not invent a method on `ProviderPublicationTransport`, retrofit fixture
receipts as production authority, or import a scheduler's in-progress model without
an agreed versioned projection. A coordinator contract reply is requested before
implementation. The field list above is the consumer requirement, not a unilateral
change to that shared interface.

## Corrections, Privacy, And Eventual Persistence

Append a new evidence document for changed inputs, preserving the prior digest and
reason for supersession. Never overwrite past observations to look as though they
were known earlier. Evaluate both windows at one explicit as-of or identify an
unequal-as-of comparison as insufficient; remeasure both after correction rather
than mixing an old before snapshot with a corrected after snapshot unknowingly.

Immutability is not permission to retain erased data forever. Existing commerce
privacy/retention behavior wins. Any future persistence must support invalidating
or deleting derived aggregate payloads and references when their source requires
it, without resurrecting facts from a cached document. Minimal tombstone metadata
is subject to existing retention policy, not a new indefinite audit exception.
Do not persist CRM raw profiles, hashed contact identifiers, order/customer keys,
creative bodies or provider credentials in B17. No retention migration in this
package; complete the privacy dependency before durable production enrollment.

## Acceptance Cases Before Implementation Is Qualified

- Equal inputs produce the same digest; modifying any scope/revision/window/basis,
  value, coverage, receipt or evaluator policy changes it. Caller mutation cannot
  alter a previously accepted document.
- Cross-workspace/account/connection/generation joins fail; erased/missing goal,
  mandate or source references produce explicit insufficiency.
- Acknowledged/unknown/conflicting receipts never count as verified action effects;
  fixture receipts never become live evidence. PAUSED/disabled creation never
  counts as activation or a zero-result performance experiment.
- Inclusive UTC report dates and exclusive local commerce dates normalize with
  explicit boundaries; DST and unequal months are not silently treated as equal.
- Clipped maturity, partial imports, stale/error/suppressed sources and missing days
  cannot qualify. Explicit zero days remain zero. Null numerator/denominator stays
  unavailable; zero baseline never yields infinity or invented lift.
- Different currencies/attribution/definitions/time zones fail comparability.
  Shopify totals, platform conversions and CRM revenue cannot be double-counted.
- Late refunds/conversion corrections generate a new evidence version and preserve
  as-of lineage; privacy deletion invalidates previously derived outputs.
- Known overlapping actions surface a confounder; unmonitored inventory/pricing/
  promotions remain unknown. No statistics or wording imply causal attribution.
- No executor, provider network, mandate mutation, spend reservation or activation
  is called by evaluation. All fixtures use synthetic aggregates and receipts.

Recommended first implementation after shared-port agreement: pure frozen models,
deterministic comparator, source projection adapters for existing persisted
commerce snapshots and explicitly synthetic normalized receipts, with conservative
insufficiency for unavailable production lineage. Durable enrollment, historical
ad metric manifests, production receipts and customer outcome UI are later packages.

## Implementation Checkpoint And Coordinator Reply

The first implementation is deliberately narrower than the proposed eventual
evidence graph: pure frozen consumer models/comparator and an existing-commerce
snapshot projection, with synthetic or unavailable-production receipts only.
No durable production lineage, schema, endpoint or enrollment is claimed.

The scheduler owner subsequently confirmed the planned normalized receipt fields
and same-attempt unknown-to-verified supersession semantics. The approved shared
direction is `/workspace/inlet-design/PROVIDER-COORDINATOR-CONTRACT.md`; committed
shared types must precede any dependent adapter. Production consent/mandate is
separate from the existing simulation mandate and cannot be inferred from it.
The next producer contract is specified in `historical-measurement-manifest.md`.
