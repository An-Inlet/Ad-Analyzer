# Session Automation Interfaces — 0072

Approved implementation direction; isolated base c2e43b9236a5affeca7516d37783ec80bbc0a3f0.
Migration 20261006_0072 descends from 20261006_0068. No production policy,
native financial proof, directional learning producer or scheduled activation is supplied.

## Strict Server Ports

`SessionAutomaticPolicy` contains workspace, environment, stable policy_family,
policy_id/revision, CandidatePolicyRef, explicit lifetime/cadence, allowed budget
operation kinds and a set of registered semantic-evidence profile identifiers.
All numeric parameters are required when constructing a registered policy; the
production registry is empty. Contract scenarios register only for contract_test.

`SemanticDecisionEpoch` contains source_schema, source_reference, semantic_digest,
and producer_family. A registered server epoch reader derives it from current
candidate evidence, never the browser. The reader must explicitly identify a
semantic observation, excluding observation/expiry timestamps and native state
refreshes. It is not permissible to hash the complete CandidateEvidence document.
Qualified profile revision and policy revision remain audit bindings, not epoch
reset keys. A missing epoch producer blocks admission. Association snapshots are
not directional producers and cannot be registered as such without a separate
qualified decision profile.

`SessionAutomationRuntime` composes CandidateSelectionRuntime, CandidateReviewRuntime,
policy registry, epoch reader registry, clock and original-session identity provider.
It uses existing real provider adapters; test assembly injects MockTransport.
Default runtime is None. Runtime absence maps to customer status unavailable,
reason automation_not_available; customer copy never mentions factories.

`CandidateRuntime.final_evidence_current(db, work, observation)` is a pure local,
noncommitting callback under the final workspace fence after reader IO. Explicit
feedback-dependent schemas require it. It rereads immutable evidence lineage and
rejects retraction before candidate insertion. Admission and every forward gate
continue using the0068 original-session/candidate guard, plus the automation guard.

## Durable Records

`session_automation_runs`: id/workspace composite owner key; actor and original
session digest (internal); exact mandate ID/revision/consent and ledger; immutable
policy family/id/revision/digest; environment; created/expires/next_due; stopped_at;
bounded stage/status/reason. Customer stop never erases financial history. A new
Start can replace a stopped session run but cannot consume an already admitted epoch.

`provider_automatic_decisions`: immutable id/workspace and review/workspace scoped
keys; session run; exact review/plan/candidate/policy/epoch commitments; ledger;
account identity digest/native owner key; actor; admitted/expiry; distinct authority
origin mandate_automatic_decision. Unique(workspace, environment, ledger,
account_identity_digest, native_owner_key, policy_family, epoch_digest). Account
identity binds native provider/account identity, not refresh time or connection
version, so reconnection cannot reset the same semantic signal in the same ledger.
Policy family is server registered; arbitrary customer families are forbidden.
Admission references the protected review and0068 marker; it carries no measurement
body and survives candidate erasure. No ProviderExecutionApproval is written.

`ProviderExecutionRun` adds authority_kind (default customer_exact_approval) and
nullable automatic_decision_id with scoped FK. A check enforces exactly the
historical variant or automatic variant. The selected variant never changes.
Manual create_run cannot reuse automatic runs; automatic cannot reuse manual.
Creation/activation reject automatic authority. Historical receipts, reconciliation
and settlement do not gain any replay authority from these records.

Central `resolve_optimization_authority(db, review, run_or_requested_authority,
actor, runtime, clock)` checks the exact variant after workspace/session locks,
current mandate/account/ledger/source locks and final candidate validation. An
automatic record must match immutable review/plan, live session run, policy and
semantic epoch; no fallback to a human approval row on failure. Final admission
rechecks after context/qualification IO and lock waits. Epoch insertion and run
creation are atomic; uniqueness failures do not manufacture a replacement epoch.

## Customer API And Status

Owned CSRF-protected routes under
`/api/customer/v1/workspaces/{wid}/execution/automation`:
- POST `/start`: exact mandate binding + registered policy reference only. No
  evidence, transport, financial bounds or authority union from the browser.
- GET `/{run_id}`: owned status and safe reason projection.
- POST `/{run_id}/stop`: fresh current owner/session, durable stop, no refund.

Start must be a real explicit request. Original-session semantics are returned:
"Runs only while the session that started it remains valid. Signing out stops
future changes. Stopping cannot undo a change already sent."
Status is unavailable, running, waiting, stopped, expired, or blocked; reason codes
include automation_not_available, policy_not_available, evidence_not_ready,
financial_proof_unavailable, original_session_ended, mandate_changed,
source_changed, decision_already_used, awaiting_original_reconciliation,
customer_stopped. Expose no session digests, provider raw payloads, or policy internals.
UI consumer can follow this frozen API; backend ships actual Start/status/stop.

## Runnable Worker

`advance_session_automation(engine, wid, run_id, runtime)` runs one bounded stage
with current original session, policy and mandate. It invokes actual selection,
queue processing, candidate review bridge and server semantic admission, then
existing durable optimization claim/execute. Stage IDs are persisted. Worker never
calls approve_optimization. Unknown requests retain fence/hold and block a new
emission. Explicit stop/retraction/logout is rechecked at every forward boundary;
reconciliation remains independent and cannot replay.

A bounded fairness wrapper processes at most one due run per workspace per pass;
existing ALL_DATA_SYNCS and an explicit disabled scheduling configuration apply.
This package does not authorize logout-independent delegation. Tests construct an
explicit Start with contract policies/epoch producers, then perform all3 actual
MockHTTP journeys with zero human approval rows, restart/dedup/expiry/retraction
and commit-gap checks. Native qualification and genuine mature direction remain
missing production source code/evidence, not a credentials-only gate.

### Frozen JSON Ports

`app/session_automation/contracts.py` owns the exact strict models:
- GET `/capabilities` → SessionAutomationCapabilities. `policies` entries contain
  `policy: {policy_id, revision}`, human label and environment. Default returns
  available=false, reason=automation_not_available, policies=[].
- POST `/start` takes StartSessionAutomation: `mandate` is the existing exact
  ProviderMandateBinding object; `policy` is AutomaticPolicyRef. Returns
  SessionAutomationStatus, including run_id. No body defaults grant anything.
- GET `/{run_id}` and POST `/{run_id}/stop` return SessionAutomationStatus. Stop
  has no body; it records the current stopping actor and is permitted to a fresh
  authorized owner even when the original starting session has ended.
- SessionAutomationStatus fields are run_id, status, reason, environment,
  session_bound=true, message. Message is safe customer copy. No internal evidence
  or source IDs, grants, credentials, session hashes, or mutation payloads appear.

These routes are not implemented in the typed-port checkpoint. UI may target
this schema; unavailable defaults must remain honest until backend composition
is installed and qualified.

Additive UI recovery/catalog ports: GET `/runs` returns SessionAutomationHistory
with up to20 owned safe status projections. After an ambiguous Start, the UI reads
this list rather than replaying Start. Start also deduplicates an active identical
original-session/mandate/policy intent under the workspace lock. Capabilities adds
`mandates: list[AutomaticMandateOption]` with exact server-resolved binding, label,
currency, total_limit_micros, starts_at, ends_at. UI never guesses consent/ledger IDs.

## Implemented Backend (0072)

The routes above, two protected audit tables, deferred historical-default authority
markers, current original-session admission guard and runnable worker are now
implemented. `worker.advance` composes selection, actual candidate reads, exact
review preparation, semantic admission, durable reservation/claim and the existing
Google/Meta/TikTok transports. It never invokes human approval. Run authority is
fixed by the protected admission reference; manual fallback is rejected.

`SessionAutomationRuntime` in `runtime.py` is the concrete server assembly port.
`SemanticEpochProducer.read(db, CandidateDecision)` supplies the reviewed stable
epoch from a registered environment/source/family. It is not a browser field and
cannot be inferred from catalog timestamps or policy revisions. Default assembly
returns None, the policy/producer registries are empty, and
`INLET_CUSTOMER_SESSION_AUTOMATION_ENABLED` is false. The shipped scheduler invokes
`worker.run_due` only under that explicit opt-in; ALL_DATA_SYNCS is checked before
constructing runtime and again before work. Tests inject complete contract scenarios.

A pass advances its due time before external reads. A failure before that advance
also receives a bounded60-second maintenance defer, under the workspace lock,
without changing claims, reservations, approvals or original session authority.
This prevents a revoked earliest session from permanently shadowing a later valid
session in the same workspace. This is retry scheduling, never a financial proof or
permission to replay an original provider request.

Closure explicitly stops session runs and records the stopping owner. Candidate
privacy/retraction nulls0068 links and blocks automatic forward gates. Protected
admission commitments and financial reconciliation/settlement history remain;
no raw measurement body or original session digest is exported. An empty0072
migration roundtrip works; any populated session/admission or automatic marker
refuses a downgrade that would erase authority provenance or consumed epochs.
Historical pre0072 fixtures explicitly assert missing new tables and use only the
old human discriminator; this is test scaffolding, not an application fallback.
The pre0066 Google fixture likewise omits only the later capture append after an
explicit table-absence assertion; current capture paths remain real.

### Remaining Production Work

This is a runnable original-session automatic existing-budget implementation with
actual adapters exercised over MockTransport. It is not live qualification. No
qualified genuine directional producer, calibrated production numeric policy,
native complete exposure bound or original-terminal/transition proof producer is
registered. Current native inventory diagnostics remain unqualified; lower budget,
current target state, missing resource, elapsed period and delayed reporting do not
prove original finality or release retained exposure. A distinct future semantic
signal can repeat only through existing complete ancestry/replacement accounting.
Logout-independent background delegation, automatic new campaigns/creative,
activation and emergency pause authority are not part of this implementation.

The automatic policy additionally commits `candidate_policy_digest`, not merely a
policy ID/revision: changing step/count parameters under the same reference fails
Start and current admission. Capabilities also reject unset numeric parameters and
an operationally disabled live execution runtime. Production registry-to-runtime
assembly is still unimplemented: the default factory returns None. Adding actual
qualified directional/exposure/terminal producers and assembling their authenticated
server adapters is remaining engineering, not a request for credentials alone.

### Principal-Aware Epoch Readers

`SemanticEpochProducer.authorized_read(db, principal, decision)` is an optional
server-only reader. Admission and subsequent automatic forward guards pass the
actual original `CustomerPrincipal` returned by `service.current`; they never
infer an owner/session from account scope. When present it takes precedence over
legacy `read(db, decision)`, including on failure. Legacy read remains supported;
a producer with neither callback is unavailable. Authorized readers are local,
noncommitting evidence readers, not grants or customer-provided callbacks.

Original-session and expiry checks still run after the callback before persistence
or emission. Tests mutate the original session's revoked/expiry state during the
callback and verify no admission, attempt or provider write. The production epoch
registry and default runtime remain unavailable; this port enables an authenticated
future source adapter without claiming that such a source is already qualified.
