# B17 Directional Consumer: Proposed Disabled Contract

Inspected `b9d2dce9d28a2cf2d83fdea2d8fb7af68f325439` (frozen candidate
`a4fcd3a` ancestry). This is a proposal, not an enabled decision policy. No provider
calls, calibration values, runtime edits or new migration are included.

## Current Component Lineage For Review

- PR183: bounded owned reconciliation observations; incremental terminal import is
  never independent completeness.
- PR185: immutable operational-maturity policy/evaluator and disabled producer/registry.
- PR189: read-only v3 receipt/source bridge; association, not causal lift.
- PR191/194: nonemitting candidate compiler and owned target selection.
- PR195/198/203: retained original Google response and terminal-request evidence;
  this does not establish advertising delivery onset or mature sales finality.
- PR201: v3 dependency/feedback/contribution persistence and transactional retraction.
- PR202: exact candidate-to-review bridge and forward provenance gates.
- PR197/204: independent Shopify traversal and strict publication v2; acquired evidence
  still has unresolved corrections and unavailable snapshot consistency.
- PR205: owned feedback scope, apply wrapper and bounded association snapshot.
- Scheduler successor: final-local-evidence hook `6c95a43` and session-automation
  contracts `332d7fc` are separate work, not part of inspected root candidate.

Current score is a policy-weighted store-sales association. It does not determine a
budget direction. Scope currently pools a native target's same operation kind; a
budget-set operation can contain both increases and decreases. The ordinary consumer
must inspect exact historical interventions before interpreting that score. Reading
`score > 0` as “increase budget” would invent an algorithm and ignore this distinction.

## Minimal Shared Contract

Implement new modules owned by this lane; preserve existing v3/snapshot bytes and the
scheduler's CandidateRuntime/service interfaces. No production registry is installed.

### Required Policy And Qualification

`DirectionalAssociationPolicyV1` is immutable with explicit ID, stable family,
revision/digest, environment, exact feedback policy digest, metric/currency/time-zone
basis and supported optimization operation. Initial support is budget-set only;
activation, pause, resume, creative and new campaigns are rejected explicitly.

Every numerical and mapping input is required; no production default is supplied:

- negative and positive score cutoffs, with a strict neutral interval containing zero;
- minimum active contributions (labelled contributions, never independent samples),
  maximum bounded contribution age and maximum decision lifetime;
- allowed original budget-change sign cohort (increase or decrease), and explicit
  above/below-threshold mapping to increase/decrease/no-change;
- exact calibrated scope restrictions, versioned calibration evidence digest and
  trusted qualification profile reference. Budget step size remains the existing
  explicit candidate policy, not a new score-to-money multiplication.

A local server registry resolves an immutable `DirectionalQualificationV1` for the
policy, environment and scope, or None. It must bind the exact policy/calibration,
qualified factual-producer versions and effective/expiry interval. A customer field,
owner preference or nonempty calibration digest does not qualify a policy. Contract
fixtures can register only contract_test records; live rejects fixture qualification.
The registry is disabled by default even when all numeric fields are syntactically
valid. Missing independent source assurance or authoritative timing remains a blocker
that no calibration profile may override.

The policy's interpretation is **calibrated association heuristic**, explicitly not
causal effect, ad attribution, finality, confidence interval or spending authority.
Approval of that interpretation is separate from approving measured parameter values.

### Owned Inputs And Pure Result

`read_directional_inputs` composes PR205's actual owned snapshot, current original
session and retained original reviewed plans. For every active contribution it
rechecks exact plan/request/receipt lineage, computes budget-change sign using exact
integer money values, and requires the configured cohort. Mixed increase/decrease,
zero-change, unsupported actions or mismatched cohorts block the whole result; do not
silently choose a favorable subset. Existing read bounds remain 64 contributions.

The original action's before/after amounts and declared money basis must come from
the stored plan. Provider readback timestamps are not delivery timestamps. Policy
freshness requires both genuine producer qualification and its bounded as-of facts;
assessment creation time alone cannot refresh an old source. The retained snapshot's
assessment age is an additional stale-input guard, not a maturity proof.

`evaluate_directional_association(inputs, policy_or_none, qualification_or_none, now)`
returns a strict `DirectionalRecommendationV1`: blocked/no_change/recommended,
explicit reasons, direction none/increase/decrease, policy/profile/calibration and
snapshot commitments, exact scope, bounded expiry, interpretation and no spending
claim. Blocked results have direction none. Neutral score gives no_change. The pure
mapping and all deny paths can be tested offline with explicitly synthetic qualified
fixtures before genuine sources or production values exist.

### Stable Decision Opportunity, Not A Refresh Epoch

Coordinate with scheduler's `SemanticDecisionEpoch`: producer_family and policy family
must stay stable across version/calibration changes. Neither snapshot digest, slot
revision, assessment ID, policy/profile revision, publication refresh, connection
version nor timestamps may create a new opportunity to raise spend.

Require a server-derived `DecisionOpportunityV1` anchored to the latest original
execution attempt for the exact current native budget owner and ledger lineage.
Resolve that head from durable original run/reservation ancestry, not browser IDs or
timestamp sorting. If the latest head is unresolved or lacks qualified feedback, block;
do not select an older favorable action. An initial campaign with no qualified original
action remains blocked under this particular feedback consumer.

Use stable original attempt ID as source_reference, plus original immutable request
commitment and native owner/account identity as semantic_digest inputs. Receipt
supersession, corrected publication, retraction/reapplication and recalibration for
that same original attempt preserve the semantic opportunity. Only a genuinely new
original action in the retained owner lineage can supply a new anchor. The full
snapshot/policy/profile digests remain audit/freshness commitments, not uniqueness
reset keys. This avoids re-admitting a removed-and-recreated contribution as fresh
budget authority. A server head-resolver is implementable code still required.

### Candidate Adapter And Final Fence

A disabled server adapter emits a new named evidence schema, never recasts raw v3 or
association snapshots as qualified learning. Registration requires the exact trusted
profile and `feedback_dependent_schemas` entry with the scheduler's mandatory local
`final_evidence_current` checker. The checker rereads the snapshot, qualification,
policy and original opportunity under the final workspace fence after IO, recomputes
the result and rejects any changed commitment/expiry. It performs no provider IO or
commit. Changed evidence cannot recreate a candidate erased by feedback retraction.

`CandidateEvidence.observation_count` must never receive the snapshot contribution
count. The adapter additionally requires a qualified underlying observation-basis
record, with explicit count kind, exact distinct completion commitments and source
qualification. A profile may define distinct independently reconciled completions as
its count metric; that does not mean statistically independent causal samples. The
candidate policy's minimum must be calibrated against that exact declared metric.
If the underlying count semantics/provenance cannot be proved, the adapter blocks.
The active-contribution threshold remains a separate directional-policy predicate.
A future count-metric change requires a versioned contract, not silent reinterpretation
of the existing observation_count field. No policy approval manufactures this evidence.

The existing candidate compiler still bounds money by current mandate, aggressiveness,
positive-change cap and action limits. Recommendation eligibility is not financial
qualification, customer consent, review approval or automatic-session permission.
Manual and separately approved automatic paths retain all their existing gates.

## Implementable Offline Work Versus Actual Enabling Gates

Implementable now, following interface approval:

1. Strict policy/qualification/opportunity/result models, disabled registries and pure
   mapping with boundary, contradictory-cohort, expiry and environment tests.
2. Actual owned snapshot/plan reader and durable original-head resolver; no customer
   evidence or arbitrary grouping. Test current goal/source/privacy/session changes,
   corrected/deleted contributions and unsupported native action types.
3. Candidate adapter and final-local-current checker coordinated with scheduler;
   actual DB/MockTransport composed tests for retraction and same-opportunity replay.
4. Calibration report contract validating exact policy/evidence lineage and explicitly
   unknown coverage; it records evidence, never substitutes for missing factual facts.

Still unavailable independently of that code: qualified independent full-window
reconciliation with resolved correction assurance, authoritative action delivery-time
producer, real calibration observations and approved parameter/mapping values. Current
Shopify v2 acquisition and Google synchronous completion do not supply these guarantees.
There is no external provider-limit incident preventing offline implementation here.

## Narrow Decision To Surface When Enabling Becomes Concrete

Recommendation: implement the disabled mechanism now. Before production enablement,
require a reviewable calibration artifact that chooses the explicit direction mapping
and thresholds for a named intervention cohort, reports sample coverage/uncertainty
without causal claims, and quantifies sensitivity under the already approved spend
mandate. Do not ask the owner to guess numeric settings now. If only observational
association can be qualified, obtain explicit acceptance of a labelled calibrated
heuristic; do not promise causal optimization. That future decision cannot substitute
for the missing consumer/head-resolver/source/timing code listed above.
