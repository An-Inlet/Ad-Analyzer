# Requested-Window Runtime Integration — Proposal

Base `3fba8f5`. Documentation only; no runtime activation or acceptance claim.
Depends on reviewed pure projection `f5102fa`, private evidence `1d373af`, and the
owned-reader package frozen by `c560717` (implementation still independently reviewed).
The reader's final reviewed signatures take precedence over this proposal.

## Dispatch And Module Ownership

Keep the existing default v2 policy until the final acceptance gate below passes.
Use `policy_capabilities.reporting_capability(policy_version, generator_version)`
for actual policies/documents and `ticket_reporting_capability(policy_version,
policy_digest)` for tickets. The latter reconstructs the canonical policy; tickets
have no generator field and receive none. Continue comparing configured policy
version **and digest** to each ticket. Reject mixed/unknown pairs and bundle/policy
mismatch, with no legacy fallback or alias for `"1"`.

Add consuming `generation_ports.py` rather than runtime imports from old `ports.py`:

```python
GenerationEvidence = EvidenceBundle | WindowEvidenceBundleV1

class GenerationEvidenceReader(Protocol):
    def collect(self, ticket: GenerationTicket) -> GenerationEvidence: ...

class GenerationComposer(Protocol):
    def compose(self, *, inputs: PlanInputRevision, evidence: GenerationEvidence,
                policy: PlanningCompositionPolicy, version: int,
                parent_digest: str | None, generated_by: str,
                generated_at: datetime) -> PlanVersion: ...
```

These are consuming annotations, not a new client/Pydantic union or persisted
schema. Existing old ports remain import-compatible; ports must not runtime-import
policy_capabilities/window_evidence/generation_ports. No runtime forward-reference
resolution is needed. Prefer separate `OwnedWindowEvidenceReader` in
`window_adapter.py`, `recheck_window_sources` in `window_local.py`, and v3 pure
composition in `window_composer.py`. Existing v1/v2 reader and composer branches
retain their bodies and accepted DTOs; never convert a window bundle into a fake
legacy bundle or a sliced report into a fabricated old report.

Concrete dispatch sites:

- `PlanningDocumentService.generate`: select reader/composer by canonical configured
  capability; ticket creation, original session, CAS, two identity-refresh boundaries
  and request receipt semantics remain unchanged. Existing v1/v2 branches accept only
  EvidenceBundle; v3 accepts only WindowEvidenceBundleV1. Mismatch is controlled409.
- `service.recheck_generation_sources` and `repository.save_generation` callback
  annotations use GenerationEvidence. Existing common attributes remain identical.
  Repository still revalidates actual bundle with `assert_ticket`, requires exact
  candidate reference set, goal/targets/privacy, current ownership/paid-work and CAS.
  Explicitly require candidate.generator_version to match the canonical ticket policy
  as well as the existing candidate.policy_version check; do not rely only on the
  outer service check when the repository is invoked directly.
- Existing `DescriptivePlanComposer` can dispatch to the separate v3 composer after
  strict pair/type checks. Do not run old `reported_summary` on a window document.
- Retained `capture_retained_sources` selects qualified state/kind from the actual
  document pair: v1 -> existing local_reporting_v1; v2/v3 -> existing
  local_reporting_v2. `_recheck` already reconstructs capture and exact row sets;
  preserve this path and reader-role authorization. No witness schema/domain/state
  changes, new default fields or source date rewriting.
- Keep `EvidenceBundle.assert_ticket` old-policy acceptance untouched except an
  explicit reject of v3 if needed at the consuming dispatcher; the new bundle's
  independent frozen validator already requires exact canonical v3. Old v1/v2
  contract hashes and plan outputs must not change.

The existing test setup policy strings `"1"` are not production versions. Only when
these consuming sites adopt closed dispatch, update that fixture to canonical v1
policy/generator and its actual digest, plus dependent expectations. Do not change
existing golden artifacts to conceal runtime drift or add `"1"` compatibility.
Keep deliberately injected fake test policies outside real production closed dispatch
when exercising isolated repository/protocol mechanics, or migrate the affected fixture
and expectations explicitly if it traverses the production dispatcher. Do not broaden
legacy contract acceptance or require unrelated repository test doubles to masquerade
as configured production policy. The new direct repository generator-binding check
must use its reviewed configured-policy seam, not silently impose a new universal
closed-policy constraint on historical/injected protocol tests.

The pure-contract test
`test_legacy_policy_digests_unchanged_and_runtime_v3_disabled` intentionally asserts
composer refusal before integration. When the separately reviewed composer accepts
explicitly injected v3, retain its exact v1/v2 policy hash assertions, replace the
now-superseded refusal assertion with positive injected-v3 composition coverage and
an explicit production-service-default-v2 guard. Keep that default guard until the
separate activation commit and replace it there with reviewed activation acceptance.
This is a planned phase transition, not a removed regression or ignored red test;
unknown/mixed policy and wrong bundle-type refusal tests remain throughout.

## Collection, Full Slot Coverage And Deadlines

The new adapter uses the same configured owned native catalog and retained receipt
paths, current goal/customer context, original session checks, and Shopify reader as
the existing adapter. Reuse through small independently tested internal helpers if
necessary; do not obtain these values by constructing an incomplete old bundle.
External catalog/identity IO stays outside database transactions. Preserve all three
platforms and their actual native scopes, including Google adgroup metadata and
unknown social budget ownership. Receipt-bound selections stay exact and expiring.

1. In the initial fresh read transaction, validate ticket/goal/source fences and
   capture ReportingPresencePin for **every** selected account, including explicit
   absence. Close it before native IO. No context survives this transaction.
2. Read/reuse exact owned catalogs and determine primary plus optional comparison
   windows. Preflight the complete campaign × window product (or one catalog-only
   gap per window for absent/empty catalogs). Refuse >400 combined successes/gaps
   before assembling partial output. Do not select only fixed allocations or drop
   excluded campaigns from source slot coverage.
3. For each actual catalog account, open a fresh hardened PlanningReadContexts
   transaction. Prepare one `OwnedWindowReadContext` with exact account/source fence,
   original collection pin and current authority. Use its context manager; share
   its one presence parse from pin through all campaign/window reads. Each exact
   campaign target/window yields RequestedWindowPerformanceV1 or KnownWindowGap.
   Unknown auth/source/manifest/privacy/DTO/capacity failures abort, never become gaps.
4. Bind each success with `reporting_entry_key` and the original manifest/generation/
   completion, new projection schema/digest and actual requested window. Expiry is
   the actual minimum native catalog deadline, not an invented reporting TTL. Partial
   selected values may be reported_only; only the frozen complete-zero predicate
   permits a no-selected-conversions-for-the-requested-window statement. Empty
   requested subsets are unavailable even if the original contains other days.
5. Bind every gap to its exact account pin/window and catalog campaign, except the
   two frozen catalog-only null-target reasons. Preserve comparison gaps even when
   primary succeeds. Google/TikTok current legacy reports without a presence sidecar
   produce reporting_presence_unavailable for each slot; retain their native catalogs
   and existing independent legacy reporting behavior, never selected-zero fallback.
6. Collect commerce and exact persisted customer/configured policy context with the
   unchanged actual source deadline rules. Construct WindowEvidenceBundleV1 and call
   assert_ticket. Enforce its full serialized32MiB cap, including originals, catalogs,
   contexts and all fields. No partially returned bundle or silent truncation.

The early pin and later read necessarily use different transactions/contexts. Final
commit uses new contexts again. Recognition of pure v3 types does not prove source
ownership; only these real owned readers and current checks do.

## Final Transaction And Retained Currentness

`recheck_window_sources(db, *, principal, ticket, bundle, now) -> None` is DB-only.
Revalidate the exact bundle/ticket and configured canonical capability. Keep existing
local authority, confirmed-goal definition, owned account/source fences, privacy,
actual catalog money/time zone, saved receipt binding and commerce reconstruction.
Preserve fresh closed-day coverage/retention/watermark checks and final effective time;
do not reuse an earlier provider decision or original collection objects as authority.

For each selected account, create a **fresh** owned context under retained locks and
recompute the original full account pin before any cache hit. Reconstruct every exact
success and every reader gap; compare full projection fingerprints or exact reason,
account, target and UTC-normalized window. For an empty retained catalog, verify its exact validated zero-campaign scope and
owned source/receipt bindings. An external collection-time `catalog_unavailable`
result is different: apply the collection-gap rules below; do not claim to re-prove
current provider absence in a DB-only transaction. Require the complete exact slot
set again. A former gap becoming available is a change, not permission to accept a
subset. Changes outside both requested slices still alter the full source pin.

Close all contexts/observers before repository updates, flushes or commit. Closing
context observers does not release retained SQL locks. After recheck, the existing
retained-source capture revalidates full source state for persisted witnesses. It may
perform another whole presence read; no claim of one parse across the entire final
service operation is made. Avoid cross-callback cache plumbing in this first package.
Final authority five-second/session and evidence-expiry checks remain after all waits
and before acceptance; any denial rolls back version, dependencies, head and receipt.
No retry/identity/provider IO occurs under locks. RawSQL/providerIO prohibition is a
caller obligation, not an advertised arbitrary-code sandbox.

History/current reads keep exact full dependency-set validation. v3 uses unchanged
local_reporting_v2 witness bytes, including whole graph or absence, native mappings,
current completion and privacy. No need to reconstruct discarded transient gaps from
freeform text. Ordinary source revisions make history stale; semantic erasure still
deletes the existing plan graph. Read-only viewer/history semantics remain unchanged.

## Pure Descriptive Composition Without Public Schema Changes

Use existing PlanVersion/ManualAction/EvidenceRef/section_limitations fields; no new
public comparison DTO or UI. Preserve original input reporting/comparison windows.
References contain **all** successful primary and comparison projection references,
not only those selected for action assessment. Policy/customer context and native
catalog references remain explicit. V3 action selection uses only exact primary-window
slots for that campaign; it never reads original full-window totals for assessment.

For a campaign review rationale, render separate literal labeled blocks:

- `Primary [inclusive local dates], [timezone], [currency], selected event [ID]:`
  requested summary observed clicks/spend/selected count and present/requested days,
  per-metric coverage and missing calendar days; unavailable cells remain unavailable.
- `Comparison [its own dates/timezone/currency/event]:` the corresponding summary or
  exact bounded known-gap reason. State that these are provider-reported observations,
  periods may have different lengths, attribution is unknown and no causal or
  normalized improvement is assessed.

Use exact integer/Decimal formatting under fixed context; never float conversion,
percentage changes, CPA/ROAS from incomplete data, rankings, forecasts or Shopify
attribution. No cross-account/platform aggregation. Original queried interval remains
available in the source explanation, distinct from requested analysis dates; it is
not relabeled as a provider query for those dates. Cite both successful references
in the action's evidence_keys; a gap has no fabricated report reference.

Persist **every** window gap through deterministic compact section limitations.
Group by the exact tuple `(account identity, UTC-normalized requested window, reason)`;
within each group list every exact provider-native campaign ID in numeric-string
lexicographic order (never names or omitted counts). Include account/platform, window
boundaries/timezone and reason in each group's readable prefix. Catalog-only gaps
have an explicit catalog-level scope, not an invented campaign ID. Keep the full
validated gap set in memory for final recheck; grouping only changes presentation.

Sort groups deterministically by account, UTC window endpoints and reason. Append
whole IDs separated by a fixed delimiter until the next complete ID would exceed
2000 characters; then start the next limitation with the same full group prefix.
Split only at ID boundaries, repeat enough group context that each fragment is
unambiguous, and verify the inverse grouping expands to the exact original slot set.
Do not truncate IDs, substitute display names, collapse differing windows/reasons,
drop campaigns/counts, or emit only a representative sample. This permits common
Google/TikTok absent-presence cases with dozens of campaigns and comparison windows
to remain useful descriptive plans with their native catalogs intact, rather than
charging one of30 limitation slots for each gap.

Preflight the grouped strings **together** with existing constraint/catalog/creative
limitations against30 entries and each Text<=2000; also retain actions<=100,
evidence_keys<=20 per action and whole canonical document<=1MiB. Worst cases include
many distinct reasons/accounts/windows, long native IDs and prefixes, and customer
constraints already occupying slots. If a full grouping or either labeled rationale
still cannot fit, fail with a bounded capacity conflict and no new version/head/receipt;
never silently shorten facts. Tests must cover ID-boundary splitting, all identities
roundtripping, repeated prefixes, stable ordering and genuine aggregate capacity
failure. Campaign exclusions do not remove campaigns from source slot coverage.

Default-v3 activation additionally requires representative existing v2 workflows to
remain meaningfully usable, especially Google/TikTok accounts with at least dozens
of campaigns and an optional comparison. Scope-reduction advice is not a substitute
for that compatibility gate. If the unchanged public document cannot represent their
complete coverage meaningfully, keep production default v2 and freeze a separately
reviewed public coverage contract before activation; do not claim the limitation is
solved by telling customers to remove accounts or comparison windows.

Preflight all persisted references **together**: successes + native catalogs +
customer/policy contexts + optional commerce must fit400, independently of the
bundle's400 success/gap bound. No `[...][:400]`/`[:30]` fallback. A valid bundle is not
necessarily representable by the bounded public plan. Return controlled409 with no
new version/head/receipt on these capacity failures. Existing alternatives, budget
ceilings, creative facts/hypotheses and zero-ad-write policy remain unchanged.

## Ordered Implementation And Activation Gates

1. Independently close owned reader package; freeze additive generation ports and
   new adapter/rechecker signatures. Update closed dispatch fixture only in this
   integration package. Keep production default v2.
2. Qualify actual collection/final recheck under explicitly injected canonical v3,
   then pure v3 composition with exact full reference/gap retention, compact
   lossless grouping and genuine capacity rejection. Preserve fixed v1/v2 report, policy and canonical plan golden bytes.
3. Actual Meta MockHTTP **56-day new-window import through the0090 producer**, then
   owned API create/generate with seven-day primary and preceding seven-day comparison
   on SQLite/PostgreSQL. Assert original header remains56days; distinct requested refs,
   positive100/10/USD100 and true-zero/missing distinction; literal comparison/gaps;
   current/history/artifact export retains both windows. No installed sidecar shortcut.
4. Actual Google/TikTok catalogs and legacy imports without sidecars: explicit per-slot
   presence gaps, retained native scope, no fabricated selected facts. Include dozens
   of native campaigns with comparison and assert meaningful grouped coverage within
   the existing document bounds, not a15campaign regression. Include primary
   success/comparison gap, absent current report, no local campaign, empty catalog,
   out-of-range/unaligned/open period and corrupted sidecar aborts.
5. Races/adverse cases on bothDB where meaningful: source generation/current pointer,
   same-pointer sidecar/body corruption, native mapping, privacy, fact outside both
   slices, absent->present/comparison gap->available, receipt/session/goal change,
   billing/owner revocation and real lock-wait final authority expiry. Reject all
   partial version/receipt writes and preserve read-only history/viewer behavior.
   Verify contexts close on success/error before flush; fresh final contexts never
   reuse initial caches; no providerIO underSQL, no added ad-write requests.
6. Run affected legacy golden, service/API, receipt, retained source/lifecycle/archive
   regressions and required static checks. Only after independent review and terminal
   actual customerAPI acceptance may a separately explicit reviewed commit change
   service default policy/generator to canonical v3. No environment toggle, migration,
   live provider call, new UI control or comprehensive-quality claim follows from it.

These are proposed implementation seams and acceptance requirements, not completed
behavior. Source-window availability and descriptive comparison do not establish
optimized allocations, expert recommendation quality or causal sales performance.


## Addendum: Collection-Time Catalog Failure Is Not Current Provider Absence

A `catalog_unavailable` window gap means only that this operation's authorized
collector returned an explicitly allowed unavailable outcome. It does not assert
that the provider currently has no campaigns or is still unavailable. Generic HTTP,
authorization, corruption, capacity or source errors still abort; do not convert
those exceptions into the allowed outcome. `no_catalog_campaigns` instead derives
from an actual validated catalog's declared native scope, not global absence.

The adapter constructs the catalog EvidenceGap and corresponding window gaps
server-side in the same collect call. The transient WindowEvidenceBundleV1 binds
operation_id, exact input_digest, privacy revision and exact selected accounts;
assert_ticket binds these to the genuine GenerationTicket, whose actor/session and
source fences came from the authenticated service. Keep the exact collected bundle
inside the service call, never deserialize it from a client or reconstruct it from
an explanation string. Final account reporting-pin equality additionally protects
local reporting/source state, not native provider availability. These are trusted
in-process provenance boundaries, not a cryptographic attestation that arbitrary
DTO construction can establish.

A collection-time catalog gap creates no fabricated catalog observation, expiry or
source digest. At least one real successful catalog is still required by this first
adapter/composer path. All-catalogs-unavailable aborts because there is no actual
native deadline; do not invent a TTL or persist an otherwise unbounded gap-only plan.
The whole bundle/candidate uses the actual minimum successful catalog/evidence
deadline and final current time checks. An unavailable account's gap remains tied to
its original selected source fence and full reporting pin, plus this operation's
other real evidence deadline. It does not borrow another account's ownership proof.

The DB-only final recheck can repeat original actor/session, input/head CAS, current
membership/paid-work, goal, privacy, exact selected account/integration/source fence,
full reporting pin and saved receipt checks. It can compare the unchanged trusted
collection gap's account/window/reason slots and its operation/input binding. It
**cannot** repeat the external collector outcome or prove continued native
unavailability; no hidden provider call or blanket currentness claim is permitted.
Retained history preserves grouped text explicitly labeled `catalog collection
unavailable when this plan was prepared`, not `provider currently unavailable`.
Retained local witnesses detect local changes only. This package adds no separate
durable native-failure receipt: immutable plan inputs, evidence references, grouped
gap text and existing source witnesses are the retained artifact, while the exact
operation-bound bundle is transient. A future need for independent durable provider
failure attestation requires a separately reviewed contract, not an inferred proof.

## Addendum: Real-Ticket Seam For Pure V3 Composition

Recommend the narrow explicit real-ticket parameter rather than splitting validation
and risking drift in the new bundle's exact-slot invariants:

```python
class WindowPlanComposer:
    def compose(self, *, ticket: GenerationTicket,
                evidence: WindowEvidenceBundleV1,
                policy: PlanningCompositionPolicy,
                generated_at: datetime) -> PlanVersion: ...
```

The service passes its actual prepared ticket unchanged. The pure composer revalidates
ticket, evidence and policy; requires exact configured policy version/digest and
canonical v3 capability; calls evidence.assert_ticket(ticket); and derives inputs,
version=expected_version+1, parent_digest=expected_parent_digest and generated_by=
actor_id directly from the ticket. It receives no independently conflicting copies
of those fields and fabricates neither ticket nor legacy bundle. It still performs
current generated_at versus evidence expiry checks; pure validation does not check
live session/ownership and does not replace the final DB authority boundary.

For v1/v2, keep the existing DescriptivePlanComposer signature and behavior unchanged.
Service dispatch calls either that legacy composer or this ticket-aware v3 composer;
there is no requirement that these two signatures share one structural Protocol.
Revise the earlier proposed GenerationComposer protocol accordingly: use separate
LegacyGenerationComposer (existing signature) and WindowGenerationComposer (above),
or explicit concrete factories at the service dispatch site. The shared evidence
union remains useful for repository/recheck annotations, but does not justify a
fake uniform composer call. Any future uniform orchestrator must itself accept the
real ticket and explicitly adapt its scalar fields to the legacy call, without
constructing a new ticket. This is the recommended minimal interface to freeze
before implementation.
