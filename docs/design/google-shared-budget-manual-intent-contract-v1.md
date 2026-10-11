# Google Shared Budget: Exact Retained Observation And Manual Intent

Design-only proposal on `3fc8670`, informed by the actual Q06 baseline `fe61767`.
No implementation approval is inferred from this document. No new default policy,
provider write, automatic amount choice, financial qualification or live claim.

## Scope And Economic Decision

First profile: Google DAILY budget, USD or another exact same account/confirmed-goal
currency, micros, observed enabled STANDARD budget, enabled/paused campaigns,
non-increasing **relative to the observed snapshot**, explicit customer amount.
No monthly-allocation-to-daily arithmetic. No shared budget interpreted as a hard
period cap. Native snapshots are non-atomic and external writers can change them.

Recommended conservative first behavior: expose a single owned-budget **review**
with the full affected set and the customer's requested daily amount as a labeled
hypothesis, but keep `native_budget` unavailable and no proposed native field while
period economic compatibility is unqualified. A separate prerequisite asking the
customer to review economics does not itself prove the amount fits the mandate and
must not silently turn it into an apply instruction. This is a useful manual review
slice, **not full positive Q06 native-edit acceptance**. Root must explicitly approve
this boundary before production implementation; an exact positive edit would need
an additional independently reviewed economic-compatibility contract.

Input rules still enforce `0 <= requested <= observed_current`, exact currency,
DAILY cadence and one independently reconciled customer alternative. Confirmed
zero ceiling rejects any positive request; zero is accepted only as a hypothesis,
not a claim Google accepts a zero budget. Provider minimums/validation remain
unqualified. The unchanged Q08 preparation path never gains an amount instruction.
An intervening lower external budget makes even an originally decreasing request
an increase relative to the new state: manual steps require fresh owner/topology/
amount inspection and stop on any mismatch, with no CAS or prevention guarantee.

## Cycle-Free Typed Modules

`google_budget_intents.py` imports only common primitive aliases/Frozen and Pydantic:

`GoogleDailyBudgetIntentV1(Frozen)` fields, in this order:
- `schema_version: Literal['inlet.google-daily-budget-intent.v1']`;
- `account_id: Positive`;
- `owner_selection_id: Digest` (server-derived opaque selection, not native ID);
- `expected_observation_digest: Digest` (discovery/input provenance only);
- `expected_owner_facts_digest: Digest` (fresh-read semantic comparison);
- `scenario_key: Key` (exact supplied customer alternative);
- `currency: strict /^[A-Z]{3}$/`;
- `cadence: Literal['daily']`;
- `unit: Literal['micros']`;
- `requested_amount_micros: Amount` (strict integer, existing bound).

`ResolvedGoogleDailyBudgetIntentV1` adds `owner_key: Digest`,
`representative_canonical_key: Digest`, `observed_amount_micros: Amount` and
`source_binding_digest: Digest`, all resolved by the server from the selected full
catalog. It retains the original selector/observation digest/owner-facts digest/scenario/currency/cadence/request.
No client-supplied resolved object, account generation or affected set is accepted.
This module cannot import context/ports/documents, avoiding PlanInputRevision cycles.

`google_budget_owner_contracts.py` imports CatalogEvidence, common and context
TargetRef, never ports/documents/repository. `GoogleDailyBudgetOwnerWitnessV1(Frozen)`:
- `schema_version: Literal['inlet.google-daily-budget-owner-witness.v1']`;
- `catalog_evidence: CatalogEvidence` (complete original projected graph);
- `owner_key: Digest`;
- `representative: TargetRef`;
- `affected_campaigns: tuple[TargetRef,...]` (2..200; ordered canonical identities);
- `current_amount_micros: Amount`;
- `currency: strict currency string`;
- `cadence: Literal['daily']`; `unit: Literal['micros']`;
- `reference_count: strict int 2..200`;
- `explicitly_shared: Literal[True]` with strict primitive check;
- `budget_status: Literal['ENABLED']`; `budget_type: Literal['STANDARD']`;
- `atomic_snapshot: Literal[False]`, strict primitive; no-authority fields unchanged.

No native budget resource URL is invented from the owner hash. The owner key is the
existing source-scoped projection identity; original inventory/request hashes are
opaque cross-bound commitments, not reconstructed raw provider transcripts.

## Derived Affected Set And Exact Profile

Pure constructor `derive_google_daily_budget_owner(catalog: CatalogEvidence,
 owner_key: Digest) -> GoogleDailyBudgetOwnerWitnessV1` revalidates copied nested
models, never trusts caller members. Known ineligible coverage/profile uses a fixed
`GoogleBudgetOwnerUnavailable` domain error; malformed graphs remain validation
failures, not absence. Derive all matching native campaign owner references and
join to composite metadata by native_settings_key and full Google advertiser/native
identity. Never match names or only campaign ID across advertisers.

Require native campaign coverage exactly complete/provider_campaigns, plus complete
campaign metadata mapping. Native adgroup settings may remain unavailable; named
children do not establish budget membership. All affected non-REMOVED campaigns
must resolve exactly; settings must agree in amount, DAILY period, absent total
amount, ENABLED/STANDARD budget, explicitly_shared true and reference count.
The count must equal the complete observed non-REMOVED owner member count, matching
the collector's `status != 'REMOVED'` predicate. For this first actionable review
profile, reject unknown native campaign statuses; accepted active members are
ENABLED or PAUSED. REMOVED rows remain in the full witness, but are excluded from
active affected_campaigns and count. If their budget setting projections conflict,
fail rather than silently choose one. Exactly one representative is the smallest
canonical key among all affected members; the user cannot choose a misleading one.

Both A and B appear even if only A carries the scenario's single owner allocation.
Any excluded member makes the intent unavailable: no covert effect on an excluded
campaign. Excluding an observed child also blocks its ancestor owner's intent,
using exact owned parent identity; unknown parentage prevents qualification. Never
count children as separately budgeted spend. Independent campaign C remains another
owner and another allocation. Duplicate aliases/member IDs, missing owners,
reference-count mismatch, nonempty page omission or unresolved joins cannot produce
a complete witness. Full metadata does not repair incomplete native coverage.

## Strict Time, Commitment And Size

Strictly validate original aware datetime values before coercion, including copied
nested models; reject numeric/bool timestamps. Compare all instants in UTC without
restamping original serialization used by native/metadata/composite digests.
Recompute projected metadata/composite commitments using existing validators,
validate full source/account/connection/version/reporting-window linkage, and check
native/reference/metadata observation ordering and exact minimum expiry in UTC.
Original observation end <= generation time < expiry, input/ticket/collection
chronology unchanged, and document.valid_until <= original expiry.

Witness canonical JSON <=256 KiB, max20 owner witnesses per plan, all enclosing
existing action/evidence/document caps preserved; reject overflow without truncation.
`digest()` revalidates and domain-separates the entire canonical original graph.
Source binding, account, privacy, generation, declared coverage and monetary units
are thereby explicit and cross-bound, not authenticated merely by a self-hash.

## Customer Discovery, CAS And Resolution

Extend the existing owned target-catalog response with an optional server-only
`google_budget_owners` list (max20). Each qualified entry shows a named representative
and all affected named campaigns, exact current daily amount/currency, observation
interval/expiry, and opaque owner_selection_id/observation digest. Existing default
responses omit this list until the capability is explicitly selected; no raw numeric
IDs become required UI input. Unsupported entries need bounded availability reasons,
not a fabricated eligible selection.

Selection commitment domain `inlet.google-budget-owner-selection.v1` binds original
owner actor/session, workspace, account/source generation, full catalog digest,
owner witness digest, and exact reporting dates; session commitment remains private
and excluded from normal serialization. Follow current original-session catalog
patterns, no client-authored scope. Expiry is the original minimum catalog expiry,
not extended by discovery or redisplay. No secret/context getter or persistent
browser token storage.

`CustomerInputs.google_daily_budget_intents: tuple[GoogleDailyBudgetIntentV1,...]
| None = None` max20, omitted when None. New resolved counterpart on PlanInputRevision
has the same omission rule and max20. Absence preserves all legacy bytes; explicit
empty is distinct only for opted-in capability. Limit new intents to exact genuine
V5 initially; reject them on old policy pairs rather than silently discard.

Create/revise use existing request_key, input revision and version CAS. Exact prior
receipt returns before current catalog lookup; changed key reuse rejects. Fresh
admission revalidates original session/owner, paid/privacy/goal/source and selected
catalog outside/final SQL as existing APIs do. Resolve the complete witness and
matching alternative. Enforce one intent per account+owner **across the plan** for
this slice; reject even duplicate identical entries, and reject conflicting amounts
rather than depend on current action conflict deduplication. Different alternatives
are not combined: the single intent names exactly one scenario, whose one owner
allocation stays within that alternative's confirmed ceiling. Fixed allocations
remain mandatory; no second A/B or child amount is added as native spend. An intent
cannot attach to the synthetic composer-generated fixed-and-unallocated scenario.

## Output, Save And Historical Binding

Add an optional, omitted-by-default owner review attachment on ManualAction:
`google_daily_budget_review: GoogleDailyBudgetReviewV1 | None = None`.
A cycle-free review model contains the exact witness, resolved customer intent,
`economic_compatibility: Literal['unqualified']`, and
`instruction_status: Literal['review_only_do_not_apply']`. It imports no action or
PlanVersion type. Default omission must work in Python/JSON and nested serialization.
Do not put the requested amount into supported ProposedField or NativeBudget.
The action remains budget_review with UnavailableBudget explaining that period
compatibility is unqualified. One representative target, one action per owner;
attachment renders the full affected set. Recovery explicitly asks for complete
owner membership, fresh amount/currency/cadence, then economic review; no guessed
setting or automatic publish. This adds an observation/hypothesis, not native advice
qualified as safe within the ceiling.

`validate_google_budget_reviews(inputs, actions, evidence, generated_at, valid_until,
 privacy_revision)` checks unique owner, exact input intent/scenario, affected-set/
exclusion/zero-ceiling rules, retained evidence/ref/target/time/currency and explicit
unqualified status. `assert_google_budget_review_bindings(actions, catalogs)` checks
full canonical original witness graph equals the actually collected catalog.
Composition and final save call both independently before mutations, after replay
earlyreturn; unexpected failures propagate through the existing narrow boundary.
Fresh original-session, goal, paid, privacy and source checks remain unchanged.

Stored PlanVersion parsing/history/export recomputes retained graph/membership/
intent/arithmetic/time joins and digest; missing/tampered witness cannot silently
become a generic review. History does not reread current native state or demand paid
entitlement. Later topology may differ without rewriting original observations;
existing persisted-fence currentness is not fresh proof against external edits.
Existing immutable row digest, captured dependencies and erasure protect the graph.

## Implementation Order And Qualification Before Any Enablement

1. Independent review resolves root's economic boundary; freeze this exact contract.
2. Standalone primitive intents/witness derivation and omission/import goldens;
   no API or composer yet. Actual baseline fixture provides profile inputs.
3. Owned discovery/admission original-session/CAS ports plus actual negative API
   fixtures; no request may resolve foreign or stale membership.
4. Pure single-owner review composer/document validation and actual save binding,
   then actual API/current/export/replay and metadata-independent partial failure.
5. Customer portal renders current/requested amounts as distinct review facts and
   every affected member; cannot display an Apply recommendation or cap guarantee.

Tests cover exact A/B membership+C independence, REMOVED predicate, unknown status,
foreign generation/currency, excluded member/child, duplicate/conflicting intents,
zero ceiling/positive request, increases vs observed amount, copied model/UTCfold/
expiry/size, stale discovery/session/CAS, save witness substitution/atomic rollback,
legacy bytes and retained historical graph after later changed membership. No full
positive Q06 claim follows from this conservative review-only slice. The remaining
exact-native-edit/economic-compatibility gap must remain explicit in readiness.


## Root Review Refinements: Binding Across Separate Reads

First implementation scope is **standalone** primitive intent classes, full owner
observation class and pure derivation/commitment helpers only. No existing context,
request, action, capability, composer, API or persistence field changes in that
slice. Future consumer fields above are proposals requiring separate review. Keep
primitive intent imports common-only; full witness imports CatalogEvidence/TargetRef
but must never be imported by context. No broad AccountRef extraction is proposed.

`owner_facts_digest(witness: GoogleDailyBudgetOwnerWitnessV1) -> Digest` first strictly
revalidates and derives a canonical object with exactly:

- schema/profile literal `inlet.google-daily-budget-owner-facts.v1`;
- workspace, account, connection, platform, connection_version and source_binding;
- owner_key, currency, time_zone, budget amount/absent-total/period/status/type,
  explicitly_shared and reference_count;
- ordered **all represented owner campaign rows**, including REMOVED rows, with full
  advertiser/native reference, canonical key, name/name_status, metadata status and
  entity_type, and their exact full projected GoogleSettingsV1 values;
- ordered active affected canonical campaign identities; removed policy literal
  `collector_status_not_removed_v1`;
- recognized native/metadata campaign coverage status/scope/reasons/counts.

Use existing domain-separated canonical hashing, strict primitives, and no ordering
by display name. Include mutable represented metadata because a newly renamed or
status-changed member must be reselected under this conservative first profile.
Exclude observation timestamps/expiry, source request/composite/inventory digests,
selection keys (which include those digests), and ref keys. They belong to their
original full witness, not stable facts. Source/privacy/reporting window still must
be checked separately and exactly on every boundary; excluding them from this facts
projection never waives those checks. Full raw query semantics unavailable in the
projection are not manufactured. Children are not owner members; exclusion checks
must independently use the entire fresh catalog's parentage.

Discovery binds its original full witness digest AND this facts digest into its
opaque session-bound selection. At input save, compare the requested discovery
observation exactly with its original owned receipt and persist original full
witness provenance. At later generation, collect a **new** witness and require its
owner_facts_digest to equal the resolved input's expected_owner_facts_digest, with
current source/privacy/reporting/expiry independently valid. The new full witness
is embedded in the generated review; never demand equal observation/composite
hashes across these separate acquisitions and never restamp or reuse an expired
old envelope. Save-time comparison remains full canonical equality with that
same generation's actual collected witness.

Existing CatalogReceiptRow retains full projected catalog JSON and scoped
InputCatalogReceiptRow links. The future consumer must resolve whether those exact
receipts plus a canonical derived witness commitment suffice for original input
provenance, or whether an explicit separate owned input-proof record is required.
No lossy primitive field or dangling digest may substitute for the retained original
witness. This storage seam is **not** part of standalone implementation approval;
freeze its exact shape and lifecycle behavior before adding any context field.

Exactly one new review action per `(account, owner)` is required even for identical
amounts. Existing legacy setting() only rejects contradictions and is not a
sufficient uniqueness gate. Apply the stricter invariant only when the new proof is
present, leaving all old document semantics/bytes untouched.

Root-approved economic boundary: positive DAILY requests remain customer hypotheses
with unqualified period-ceiling compatibility and produce no actionable NativeBudget.
A manual review prerequisite cannot certify economics. A requested zero may become
an exact manual zero-setting only after separately reviewed provider-validity and
strict owner/intent/currentness plus zero-compatible period checks; **this standalone
slice does not qualify that setting**. No default automatic code or spend authority.
The future exact-positive-advice gap is a concrete product/evidence constraint, not
an owner permission request to proceed with independently useful proof engineering.

Recognized coverage clarification: native campaign AND metadata campaign entries
must each be exactly `complete`, `provider_campaigns`, no reasons, and their counts
must equal their actual represented campaign rows. The overall EvidenceRef may
remain `partial` because unrelated native adgroups are unavailable; do not require
whole-reference completeness or infer native child settings. For every owner member,
metadata status must equal its native ENABLED/PAUSED/REMOVED status. Contradictions
or unknown statuses reject; membership then follows the explicit collector predicate
and retains removed observations separately. Budget must be ENABLED/STANDARD/DAILY
in micros with total_amount_micros exactly None. Actual save compares the full
canonical original catalog despite opaque inventory hashes; self-consistent hashes
alone never establish authentic acquisition.
