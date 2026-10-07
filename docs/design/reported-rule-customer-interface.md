# Reported rule customer interface freeze

Local checked interface, 2026-10-07; follows dispatcher `3cf2d8f`.

Candidate GET `/execution/candidates/reads/{job_id}` adds `basis_details`:
null for legacy/no decision, otherwise `ReportedRuleBasisDetailsV1` in
`app/reported_feedback/customer_contracts.py`. The server validates the current
owned comparison again, then constructs the projection and reauthorizes the
original session before delivery. It includes inclusive local dates, explicit
currency/account timezone, missing dates, revision-within-tolerance flags,
separate actual completion count and original-attempt count, unsettled/noncausal
semantics, exact policy parameters and nominal before/after/delta. CPA,
conversions, reported spend and decimal parameters are canonical non-exponent
strings; null is unknown, never zero. Nominal amounts are bounded integers <=1e15.
No capsule IDs, tokens or native identifiers occur in this projection.

The dependent UI owns candidate-read.mjs, optimization.html and
session-automation.mjs. Backend owns all routes/runtime composition. Render the
basis as “Reported-efficiency rule”, disclose both observed windows and uncertain
revision/delivery/causal status, and keep existing exact Review separate. The
adjustment limit is a nominal budget-change limit, not remaining spend or a new
spending cap. Clear all stale/session/workspace/selection responses as before.

Explicit automatic interface is frozen in
`app/reported_feedback/automatic_contracts.py`:
- `ReportedRuleAutomaticPolicyOptionV1` is a separate capabilities policy variant:
  policy ref/digest, label, environment, decision_basis, rule_parameters,
  lifetime_seconds, cadence_seconds, original-session and separate-financial-check
  literals. It is not yet emitted by the runtime in this interface checkpoint.
- `StartReportedRuleAutomationV1` body on the existing Start endpoint is exactly
  schema_version=`inlet.start-reported-rule-automation.v1`,
  decision_basis=`operational_reported_efficiency_rule`, mandate binding, policy
  ref and expected_policy_digest. No evidence or browser numeric policy.
- `ReportedRuleAutomaticPolicyV1` binds the exact candidate policy digest and
  required cadence/lifetime. Stable protocol policy/epoch family constants cannot
  change on recalibration, registration, session restart or policy revision.
  These identity constants are not business numeric defaults. Existing v1 policy
  and Start bytes remain unchanged. API union/assembly/admission wiring follows
  separately; these types alone do not make Start available.

The UI must explicitly display the basis, all supplied parameters and cadence /
lifetime before Start. It must post the exact selected digest and basis, never
reinterpret an old legacy choice or automatically consent/restart. Missing actual
runtime/policy/evidence/financial proof remains unavailable; no production
policy registration is installed by this package.
