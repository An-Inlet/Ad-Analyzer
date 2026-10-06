# B17 After 0075: Configuration-Associated Operational Feedback

Read-only review of `908c9f91f058bd29ef425ca0f9b738f71a279378` in
`/workspace/inlet-mvp-next`, 2026-10-06. This proposal changes no code, policy,
registry, migration, runtime or spending gate. Original launch scope is unchanged;
there is no recommendation-only release approval.

## Acceptance And Current Position

Audit acceptance: **“Comparable mature windows update bounded recommendations with
an explanation.”** Universal provider finality, causal lift and independently proven
ad-delivery onset are stronger promises than this sentence requires. They must not be
claimed, but their absence need not prohibit an explicitly different operational,
configuration-associated recommendation contract.

| Actual code | What it provides | What remains |
| --- | --- | --- |
| `campaign_performance/service.py`, `aggregate.py`, Meta/Google/TikTok importer terminal hooks | Owned, terminal, digest-checked current report; Meta selected purchase event; weaker Google/TikTok meanings kept explicit | No persistent historical values before prospective capture; no missing-day zero inference |
| `initial_planning/capture.py`, `calibration.py`, models/0075 | Prospective retained campaign aggregates; current source checks; chronological nonoverlapping sensitivity replay; correction invalidation; explicit CPA objective | Not action-linked feedback; `evaluated` is not empirical validation or operational maturity |
| `publication/optimization.py::normalized`, `read_owned_outcome_receipt`; `executors/*_optimization.py` | Original action/request/native owner lineage, dispatch timestamp, latest exact configuration readback and observation timestamp | Does not assert actual delivery onset or uninterrupted configuration between observations |
| `outcomes/maturity.py`, `owned_v3.py` | Parameterized strict independent-commerce reconciliation and delivery-interval association | Actual inputs remain insufficient; no installed maturity policy or authoritative delivery producer |
| `outcome_feedback/{service,snapshot,invalidation}.py`, `outcomes/feedback.py` | Owned v3 contributions, idempotent slots, recomputed bounded totals, dependency/retraction fences | Storage/consumer are specifically tied to strict commerce/v3 evidence, not 0075 Meta capsules |
| `directional_feedback/{reader,evaluator,adapter}.py` | Authenticated, final-fenced strict directional candidate integration and stable original-attempt opportunity | Registered facts/profile/policy absent; cannot promote raw report stability or contribution count to independent evidence |

0075 therefore advances useful initial planning, not completed B17 action learning.
API/UI and lifecycle composition are separately delivered by the other package agents;
this review makes no new test or live qualification claim.

## Smallest Coherent Next Slice

Implement **Meta campaign-budget configuration-associated reported-efficiency feedback**
first, through an actual owner History/Initial Planning action-comparison request and
an explained, bounded preview update. Restrict to an exact campaign-level budget owner;
reject ad-set scope, pooled/shared budget extrapolation, paused creation, unknown/conflict
receipts, mismatched source epochs and unrelated tenants. No new provider write path.

The concrete chain is:

1. Resolve an owned original existing-campaign budget action and its latest receipt
   using `publication/optimization.py::read_owned_outcome_receipt`. Load its exact plan
   and before/after configuration. Reuse `directional_feedback/reader.py` lineage rules
   conceptually, but do not pretend this is the strict qualified-directional schema.
   A newer unresolved native-owner attempt blocks selection of an older successful one.
2. Collect/re-read actual Meta campaign-day reports for two server-derived fixed closed
   windows; terminal publication and `capture_current` retain each actual observation.
   Existing `meta/client.py::page(..., start, end)` already sends explicit `time_range`,
   daily increment and campaign grain. **Missing ordinary code:** an owned, bounded
   fixed-window re-observation job using `meta/sync.py` staging/terminal publication;
   today's automatic initialization always chooses a rolling 56-day window. Merely
   repeating that rolling import does not create repeat observations of the same window.
   Reuse existing source locks, pagination, credentials and terminal transaction; no
   direct mid-import checkpoint mutation or guessed provider history.
3. Derive the versioned operational assessment from retained values and the actual
   configuration receipt, then update a non-authorizing recommendation preview with an
   explicit reason. Persist dependencies so corrections/expiry remove the entire
   derived numeric assessment and contribution; do not leave dangling numeric bodies.
4. Show before/after reported CPA, observation dates, revision/stability findings,
   configuration-observation bracket, selected policy and bounded recommendation change
   together. Explicitly show insufficient reasons and `delivery_time=unavailable`,
   `causal_lift=unavailable`. Existing review handoff remains unavailable unless its
   separate durable provenance/forward-retraction seam is implemented and qualified.

An assessment-only endpoint without the explained preview consumer would be another
partial producer. Conversely, a preview using only the after-window CPA is initial
planning, not action-outcome feedback; the new feedback calculation must actually use
both qualified comparable windows under an explicit policy.

## Proposed Concrete Shared Interfaces

Use separate names; preserve old schema bytes and gates unchanged:

- `ConfigurationObservationAnchorV1`: owned original attempt/request/plan/native-owner
  commitments, latest receipt ID/digest/sequence, `dispatched_at`, `configuration_observed_at`,
  exact campaign cohort and before/after configuration commitments. Interpretation is
  **configuration observed, not delivery effective**. Never populate existing receipt
  `effective_lower/upper` from these fields.
- `ReportedWindowOperationalPolicyV1`: required named server policy and revision,
  explicit event/query/currency/timezone basis, acquisition-after-window-close age,
  distinct repeat-completion count, minimum spacing, bounded revision tolerance,
  maximum source age and allowed comparable window shape. Every numeric input remains
  required; no defaults, no reuse of draft 5/10/20, no claim that repeat stability proves
  independent reconciliation or finality.
- `OperationalReportedComparisonV1`: anchor, exact before/after capsule IDs/digests,
  acquisition-as-of times, comparable window boundaries, nullable factual values,
  stability/correction status and reasons. Status `operational_reported_as_of` or
  `insufficient`; this is a new operational definition, not `OwnedV3Assessment`.
- `compare_owned_reported_action(session_factory, principal, identity_provider,
  attempt_id, objective, registered_policy, clock)`: owns short DB phases, releases
  locks before any report acquisition IO, and rechecks original session/current goal,
  source, latest receipt and every dependency after IO under workspace-first fences.
  HTTP accepts IDs/intent only, never policy, timing proof, cohort or metrics.
- `apply_reported_feedback_and_preview(...)`: same owned assessment/current checks,
  required explicit mapping/weight/clamp configuration, one active contribution per
  original attempt + policy family + exact cohort. Recompute from active contributions;
  replace/retract rather than compound repeatedly. Return the actual preview and its
  explanation, with no spending authority. Do not register it as `qualified_learning`
  in `optimization_candidates/contracts.py` or reuse strict independent completion counts.

Before implementation, freeze a strict new assessment/dependency/active-slot schema
with lifecycle/export owners. Existing v3 storage depends on commerce publications and
cannot safely receive these capsule documents by relabelling. An additive schema will
likely be necessary; **none is reserved or proposed for immediate editing here**.
A report correction, superseding receipt or expiry must erase/retract every dependent
result, even when its current anchor capsule differs from the corrected historical one.
Conservative workspace-derived invalidation is acceptable initially; financial history
and settlement remain untouched. Apply retained-row caps and dual app/DB expiry clocks.

## Honest Operational Predicates

A possible implementable operational definition is: explicitly configured repeated
terminal reports of the *same closed window*, acquired after its close and required age,
within configured spacing/freshness/revision tolerances, with complete known comparable
coverage and current ownership/source, are stable **as observed**. It is not authoritative
provider finality. Corrections reopen insufficiency/recompute and retract earlier advice.

Before window ends at or before dispatch; after window begins at or after configuration
readback. Exclude the entire intervening interval. These are conservative observation
boundaries, **not a proven treatment interval**. Equal local duration/day composition,
exact campaign/event/query/currency/timezone and source generation are necessary.
Intervening known owned actions, observed configuration conflicts, missing rows, incomplete
pages, unknown counts and zero-conversion undefined CPA yield explicit insufficiency.
Do not assert that no unobserved manual provider edits occurred.

0075 retains `reported_day_count`, not all historical per-day values. A producer must
prove its retained coverage meaning from actual terminal campaign-day rows; a count must
not be treated as independent evidence or silently fill missing dates. If the proposed
predicate needs an exact coverage bitmap/day commitments not preserved in 0075, add a
new capture version with that minimal evidence; never reconstruct overwritten history.
Same-window revisions are one opportunity, not extra independent samples. Corrections,
refresh clocks, new completion IDs, policy revisions and privacy changes must not mint
another positive-spend opportunity.

## What Truly Blocks What

**Implementable offline now:** fixed-window Meta report acquisition with real mocked
HTTP; campaign-owned anchor projection from actual receipts; strict operational version;
comparison/evaluator; derived persistence/dependency erasure; idempotent bounded feedback;
actual customer preview explanation; API/browser/SQLite/PostgreSQL tests. These are
unfinished code, not external blockers.

**Required configuration/empirical decisions:** age/spacing/revision tolerance, comparable
window length, minimum usable counts and feedback mapping/clamps. Replay can report
chronological sensitivity and insufficiency, but cannot infer defensible production
values from fixtures. Recommend selecting a documented operational profile only after
examining actual retained revision histories and usable-window coverage; require explicit
approval of its stated risk of later restatement. No arbitrary parameter recommendation
is supported by current repository data. Code accepts required values without installing
any production profile.

**Provider/live qualification:** real permissions, supported query access, observed report
revision behavior and correct receipt/native-account binding. No external call is needed
to implement/test the chain. Real deployment remains a separate gate. Meta first is
concrete; Google aggregated conversions and TikTok generic conversion/unknown value need
separate explicitly confirmed objectives and reporting bases before extending this policy.

**Not required to claim this narrower operational result:** universal financial finality,
causal lift, or authoritative ad-delivery onset. These remain unavailable and the existing
strict v3/directional contracts stay insufficient. If product acceptance specifically
requires delivery-associated commerce learning, that stronger producer gap remains open.

## Required End-To-End Evidence Before Calling The Slice Done

Actual Meta HTTP pages → terminal completion → retained fixed-window revisions; actual
owned optimization receipt/configuration readback → before/after comparison → bounded
active contribution → changed explained preview. Cover correction at acquisition and
final-read races, late revisions, delayed capture of early acquisition, missing-day/zero
semantics, later unknown receipt, source reconnect, privacy/expiry, repeated requests,
cohort/tenant/session denial and stable original opportunity. Use actual adapters with
mocked wire traffic, never fabricated provider finality. Synthetic successful scenarios
prove implementation behavior only; they do not qualify production parameters or launch.
