# Operational Reported Rule: Proposed Frozen Interfaces

Proposal only, 2026-10-07; follows `3367e6f`, source `ba1e920`.
No implementation, registration, migration allocation or live-policy approval.
The first supported scope is Meta campaign-level, complete native campaign budget
owner, existing budget changes only. No adset extrapolation, creative, pause,
new campaign, first-ever decision or multi-original learning in this package.

## Documents And Compatibility

Use separate classes/modules; never extend literals/defaults inside persisted v1
models. All new documents are strict, extra-forbid, have explicit environment and
schema-domain digest, and revalidate nested values at trusted boundaries.

`ReportedRulePolicyV1` (`inlet.reported-rule-policy.v1`):
- workspace_id, environment, policy_id, revision, stable policy_family;
- feedback_policy: exact existing `ReportedFeedbackPolicyV1`;
- comparison_policy_digest, allowed_operation literal `meta_budget_set_v1`;
- maximum_candidate_age_seconds (required integer1..300).

Validate feedback environment and comparison-policy digest equality and
minimum_distinct_original_attempts==1. Existing feedback parameters are all
required: no added neutral band, weight, cutoff, minimum-data or step defaults.
`maximum_preview_delta_micros` is displayed as the rule's maximum nominal budget
adjustment; it does not change the spending cap. Reuse `bounded_delta((comparison,),
feedback_policy)`; do not apply the legacy compiler's unrelated fixed step.

`ReportedRuleEvidenceV1` (`inlet.reported-rule-evidence.v1`):
- scope_digest; environment;
- source_schema literal `inlet.operational-reported-comparison.v1`, matching the
  existing class discriminator; retain its existing class-name digest domain;
- source_reference=original_attempt_id; comparison_id, comparison_digest,
  acquisition_request_id, comparison_policy_digest, rule_policy_digest;
- opportunity: existing `DecisionOpportunityV1` (original attempt/request/native
  account/owner/ledger); direction increase/decrease/none; signed_delta_micros;
- before/after: exact `ReportedWindowSummaryV1` including capsule references,
  missing days and observed CPA; no copied raw reports or native IDs in UI;
- reported_completion_count: required4..16, number of actual distinct window
  completion IDs; original_attempt_count: Literal[1];
- observed_at, expires_at, with expiry capped by comparison, current original
  session, rule lifetime and source/native/mandate freshness;
- basis Literal operational_reported_efficiency_rule;
  correction_status Literal as_observed_unsettled;
  causal_lift/delivery_time Literal unavailable; spending_authority Literal none.

No `qualification=qualified_learning`, qualified-completion count or mature flag.
Direction must equal signed delta sign; missing/insufficient comparisons produce
blocked status outside this evidence type, never fabricated zero/hold evidence.
The full source data remains subject to existing erasure rules.

`ReportedRuleObservationV1`: scope:CandidateScope, state:OptimizationState,
evidence:ReportedRuleEvidenceV1. Require exact owned scope/state/owner/targetset,
Meta campaign topology, period/currency/environment and fresh native baseline.

`ReportedRuleWorkV1` (`inlet.reported-rule-work.v1`): scope, policy:ReportedRulePolicyV1,
selection:SelectionProvenance, comparison_id. Server creates it; customer cannot
supply work/state/evidence. Selection provenance commits the new policy digest.

`ReportedRuleCandidateV1` (`inlet.reported-rule-candidate.v1`): preserve the existing
CandidateDecision common scope/policy/state/evidence digests, status/reasons,
action, observation/expiry and three nonauthority literals; evidence is the new
type. Suggested requires exact native budget + bounded signed delta, currency
quantum, positive result and existing cumulative mandate/action/aggressiveness
limits. Do not silently increase/round a user parameter; disclose any mandated
clipping in typed reasons and nominal before/after amounts. Block unsupported
money/topology. Decision union = existing CandidateDecision OR new variant,
discriminated by schema_version. Existing decision/work parsers and digests stay
unchanged; add variants to owned read, provenance, strict export and archive
consumers explicitly. No permissive raw-dict fallback.

## Concrete Server Calls And Worker Integration

New module `app/reported_feedback/candidate_source.py`, signatures:

```
resolve_reported_work(db, principal, selection, policy, planning_runtime)
    -> ReportedRuleWorkV1 | ReportedRuleBlock
read_reported_rule(db, principal, work, native_observation, planning_runtime, now)
    -> ReportedRuleObservationV1
assert_reported_rule_current(db, principal, work, decision, planning_runtime, now)
    -> None
reported_rule_epoch(db, principal, work, decision, planning_runtime)
    -> SemanticDecisionEpoch
```

`selection` is current server CandidateWorkV2 structural selection; its v1 numeric
policy is NOT evidence or the new rule authority. Implementation should extract
its common immutable selection/scope rather than evaluating that legacy policy.
Native IO remains the existing owned optimization reader. These new source calls
are local DB-only; no commits/network under workspace/economic locks. Reader uses
current local owned comparison/dependency validators, latest original owner attempt
and original session. It cannot select a favorable historical comparison or fall
back after current-head deletion. Exactly one current same-scope comparison is
required; missing/ambiguous gives a fixed blocked reason.

The configured candidate worker invokes native IO outside locks, then this typed
source under the existing final principal fence, rechecks clock/lease/currentness,
and atomically persists the new decision. Registration explicitly identifies the
reported-rule descriptor variant, not a learning allowlist entry. Existing source
registry default remains empty; an actual test profile can be pinned for configured
HTTP/API/worker acceptance. Production registration requires separately reviewed
parameters and source applicability, not merely presence of a JSON file.

Dependency persistence must include the exact comparison/current acquisition and
capsule lineage. Genuine erasure/correction invalidates candidate jobs/results,
which already revokes linked review authority. Pure JSON IDs do not suffice for
cross-campaign/privacy deletion. Reuse existing candidate invalidation hooks where
possible; a minimal indexed dependency relation/DDL is permissible only after
schema reservation review. Preserve financial history and absent-link denial.

## Automatic Admission Union And Semantic Opportunity

Second implementation slice, after the customer candidate/review path works:
`ReportedRuleAutomaticPolicyV1` (`inlet.session-reported-rule-policy.v1`) has the
existing SessionAutomaticPolicy ownership/family/ref/digest/operation/producer/
lifetime/cadence fields, with exact new rule-policy reference and
`decision_basis=operational_reported_efficiency_rule`.

Automatic policy union = unchanged SessionAutomaticPolicy OR this new variant.
Existing `OptimizationAuthority` remains exact-human-approval OR mandate-automatic-
decision; do not forge human approval or introduce a weaker executor authority.
The existing admission row binds the new policy and decision digests and original
Start session. These rows currently store scalar commitments, not policy JSON. The
forward resolver parses the registered policy union and requires equality to the
persisted session/admission policy digest; the candidate/review provenance retains
the exact typed decision and basis. Missing registration or an unknown variant
fails closed, with no fallback to mature-learning/manual authority. Historical
evidence reads retain their existing independent path and need no current policy
registration. No admission-table migration is proposed for this type extension.

Use the existing stable original-action opportunity digest unchanged. Producer
family is stable across rule revisions; policy-family uniqueness cannot reset on
manifest/profile replacement. Reobserve, corrections, new calibration, source
refresh, consent revision or restarting Start must not create another semantic
opportunity. Recheck current comparison and session at candidate publication,
review prepare/approval, automatic admission, claim and final emission; historical
receipt/reconciliation/settlement reads cannot restore forward authority.

Configured session automation composes actual selection/review/epoch source with
this exact registered policy. Start explicitly displays this basis and remains
original-session-bound; Stop and revocation behavior unchanged. Financial exposure,
repeat closure/transition, same-period/currency/accountset accounting and native
provider qualification are independent mandatory executor checks. No inferred
zero residuals, cap increase or assumed financial finality.

## Customer Projection And Acceptance

Existing candidate status adds a versioned `basis_details` union, resolved by owned
server read (never browser hashing):
- label “Reported-Efficiency Rule”; before/after dates and reported CPAs;
- actual observations, missing-day/revision status, named policy and explicit
  adjustment limit; nominal current/proposed budget only when available;
- “Based on reported campaign results. This does not prove the change caused the
  result or predict future performance. Reports can be revised.”
- “Review Required” for manual candidate; “Financial Checks Pending” when blocked
  at execution. Never “learned winner”, “qualified learning” or “safe to spend”.

Start text: “Apply this reported-efficiency rule to the selected existing campaign
within my approved mandate while this session remains valid.” It separately shows
policy parameters/cadence and original-session expiry. New creative/campaign
approval is untouched. Actual API requests remain local mandate/policy/job IDs and
expected server digest only; no browser facts, JSON proof or provider IDs.

Acceptance uses genuine fixed-window Meta MockHTTP and ordinary configured worker
plus real customer HTTPS. Test default unavailable; actual successful candidate;
revised/missing/zero-conversion/stale reports; current-head deletion; foreign
account/goal/owner; session/source drift during IO; final retraction after claim;
exact-review/no financial bypass; same-opportunity correction/restart/policyrevision
no repeat; no numeric defaults; unchanged v1 hashes/exports/manual and mature
paths. Second slice adds automatic admission with zero fabricated human approvals,
retained original unknown/hold and truthful financial blocker. Neither slice is
live qualification or completion of first-ever automatic direction.
