# Q06 Shared Google Budget — Bounded Package Proposal

Design only on `51c7b4e`. No tests, implementation, live provider calls or default
policy changes. Q06 requires one shared setting with both affected campaigns,
no duplicated child spend, conflicting owner edits rejected, and explicit recovery
when affected-set coverage is incomplete. These criteria remain unchanged.

## Existing Facts And Missing Join

`google_native_inventory.py` reads actual campaign/budget pages and reconciles every
budget reference_count with its observed non-REMOVED referencing campaigns. Missing
budget rows or count mismatch sets `campaign_budget_inventory_changed` and makes
`advertising_inventory_read_complete` false. This is non-atomic observed topology,
not a preventive spend guarantee. `planning_catalog/projection.py` maps each campaign
to a source-scoped budget owner key and preserves amount, total amount, period,
status/type, explicit sharing and reference count. Complete campaign scope is
separate from unavailable adgroup native settings. Composite metadata may supply
child identities but cannot make missing native topology complete.

`CustomerScenarioIntent`, `BudgetScenario` and existing document validators already
reject duplicate owner allocations; `PlanVersion` rejects contradictory native
settings by account/owner. Tests `test_shared_owner_cannot_be_allocated_twice` and
`test_shared_owner_contradictory_native_budgets_rejected` exercise constructed
packets. Native inventory pagination tests observe two campaigns sharing a budget;
metadata/API tests expose shared flags. None of these is the actual V5 positive
three-campaign generation/export join required by Q06.

The selected V5 composer currently emits no exact native budget edit at all. Its
ManualAction has one target, while NativeBudget carries amount/owner but no retained
complete affected set. Existing monthly customer allocation intents cannot supply
a daily native amount: division by days would invent a provider-setting proposal.
Thus this is a real output/input/provenance gap, not a credential-only gate.

## First Actionable Slice: Actual Fixture And Negative Baseline

New local Q06 fixture/test files, leaving Q05/Q07/shared helpers unchanged. Reuse
actual Google Common Basis original owner, source/vault, goal and image; injected
read-only Google HTTP supplies A and B with one native budget and C with another.
Return a paginated campaign set (A then B/C), exact names/IDs and genuine named
metadata child-parent mapping. Shared native budget reference_count=2, explicitly
shared=true, same amount/period/status/type for A/B; independent C count=1. Use the
actual target-catalog API to obtain selectors, not manufactured owner hashes.

Two responder variants: (a) complete observed campaign topology; (b) count=3 but
only A/B observed, retaining partial coverage rather than inventing a third target.
All observations remain non-atomic. Actual V5 create/generate/current/export/replay
should currently demonstrate the unavailable exact native edit. Record that gap,
not a positive Q06 pass. Actual API intents allocating separately to A and B must
reject without input/version/head/receipt changes; A plus C is a valid independent
planning alternative. Child references must not become extra native spending.

Retain separate catalog/document/export artifacts and hashes, zero financial and
execution effects, no new native calls on replay/current/export. This fixture slice
can proceed independently once reviewed; production proposals below need their own
shared contract review first.

## Proposed Production Interfaces For Subsequent Review

1. Pure `GoogleBudgetOwnerObservationV1` retains **full original CatalogEvidence**,
   source/account-scoped owner key, one deterministic representative campaign target,
   ordered complete affected campaign TargetRefs, and exact observed native budget
   tuple (micros/currency/period/current amount/status/type/sharing/reference count).
   Constructor derives members from the full collected catalog; callers cannot
   provide a smaller chosen subset. Require complete campaign native coverage,
   every matching non-REMOVED owner reference, exact count, consistent settings,
   unique native identity and all member metadata bindings. Unknown status, mixed
   currency, unresolved owner, unsupported period/type or incomplete membership
   makes an exact setting unavailable with a concrete refresh/reselect step.
   Removed campaigns remain retained source facts but are not silently counted as
   active owner members; freeze this rule against the collector's actual predicate.

2. A separate **customer supplied native-setting intent**, not an allocation
   conversion: exact owned owner selection/digest plus requested absolute micros and
   native cadence/currency, resolved server-side from a fresh bounded catalog.
   The current UI/input API has no such port. Its exact opaque selector, CAS and
   replay shape must be designed before any positive setting recommendation.
   The default descriptive policy cannot invent an amount or claim optimization.
   An unchanged observed amount can be displayed as a review fact, but that alone
   does not close the conflicting-edit/positive-setting acceptance.

3. Additive owner-scoped action evidence on a campaign representative, with all
   affected campaigns explicit and bound to the same retained witness. Default
   omission preserves existing V1–V5 bytes. One action per account/owner, never
   duplicate same-setting actions for A and B. Reject conflicting customer intents
   before publication of a plan. Retain units/cadence exactly; daily settings are
   not overall caps or verified remaining spend. Monthly planning allocations stay
   separate alternatives and cannot be summed again with owner settings.

4. A cycle-free validator verifies full witness/model commitments, exact input
   intent, source/privacy/account/observations and affected-set equality. Composition
   and repository save independently compare the full canonical collected graph,
   not only equal digests or same-ZoneInfo datetime equality. Stored document/history
   validates retained original witness without a fresh provider read or later
   topology substitution. Existing persisted-fence currentness does not detect all
   outside provider edits; do not advertise that it does.

The new action remains manual customer planning only: no executor, spend authority,
provider mutation, automatic enrollment or default V5 switch. No economic ceiling
proof is manufactured from this owner observation.

## Negative And Compatibility Criteria

- Foreign account/source/generation/owner, duplicate aliases or name-only rebinding
  reject; parentage uses full advertiser and native IDs.
- Owner reference-count mismatch, missing page/campaign/budget, orphan child,
  inconsistent A/B amounts or unknown statuses cannot claim complete affected set.
- A and B conflicting native requested values reject atomically; exact replay is
  stable. A/B duplicate planning amounts also reject independently of this port.
- Excluding B cannot make A's shared budget independent: either retain B explicitly
  as affected and require appropriate customer scope or leave native edit unavailable.
  Never silently act on an excluded campaign through its owner.
- No child allocation counted again as native spend; native cadence and monthly
  planning totals remain distinct. Zero ceiling does not authorize an increase.
- Copied/tampered/missing witness and stale intent reject before persistence;
  historical original graph remains intact after a later changed owner catalog.
- Existing campaign/creative serialization goldens and default V3 remain unchanged.

No new consequential owner decision is required to build the baseline and propose
an explicit manual-intent port. Choosing automatic amounts or weakening the total
mandate would be outside this package. Human expert evaluation and live provider
coverage qualification remain separate; no fixture result substitutes for either.
