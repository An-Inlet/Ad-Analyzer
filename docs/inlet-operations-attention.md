# Operator Attention Evidence

`GET /api/v1/operations/attention` reuses the existing operator bearer boundary.
It returns `inlet.operations.attention.v1`, fixed codes, aggregate observed counts,
oldest known timestamps and fixed next-action categories. It performs no provider
calls, retries, reservation release, credential reads, storage requests or incident
delivery. Existing `/operations/sync-health` behavior is unchanged.

## Interpretation

The observation threshold is 900 seconds (15 minutes), an explicit engineering
attention threshold rather than a promised service-level objective. A scheduled
retry is expected until its due time is overdue by that threshold. Timestamp-less
terminal states retain a null age; an age is never fabricated.

| Code | Evidence | Safe Operator Response |
| --- | --- | --- |
| `job_failed` | Latest sampled run for an exact workspace/connection/account/platform/job identity failed; a newer success suppresses the earlier failure | Inspect the scoped job using existing operator tools; distinguish local analysis from provider collection |
| `analysis_failed` | Latest sampled terminal analysis for workspace/cadence/account failed; later terminal success suppresses it | Inspect local analysis source and failure classification; no automatic rerun |
| `analysis_running_overdue` | An independent sampled running analysis began at least 15 minutes ago, even if another run later succeeded | Inspect worker ownership; neither age nor another success proves termination |
| `job_running_overdue` | Latest sampled running job began at least 15 minutes ago | Inspect worker ownership and progress before deciding recovery |
| `billing_event_overdue` | Active-workspace pending event has no future retry, and receipt/retry due time is at least 15 minutes old | Inspect webhook reconciliation; never infer payment from browser return |
| `billing_snapshot_overdue` | Active subscription lacks recent verification and any scheduled retry is at least 15 minutes overdue | Inspect reconciliation availability; do not grant entitlements manually |
| `connection_provider_error` | Active-workspace native/source connection is terminally blocked by a provider rejection, including when no retry is scheduled | Review connection access/configuration; never replay automatically |
| `connection_reconnect_required` | Active-workspace native/source connection requires a new grant | Direct the authorized customer to reconnect |
| `connection_retry_overdue` | Persisted connection error has a retry due at least 15 minutes ago | Inspect pacing/worker state; respect account-wide cooldown |
| `renewal_outcome_unknown` | Persisted renewal uncertainty | Preserve encrypted evidence; do not replay a possibly consumed rotating refresh token |
| `publication_outcome_unknown` | Publication step is unknown/conflicting, including closing workspaces | Preserve reservations and reconcile verified provider evidence; never blindly republish |
| `action_outcome_unknown` | Mandate action outcome is unknown, including closing workspaces | Preserve reservation; investigate current authority and receipts |
| `action_dispatch_overdue` | Dispatching action has no recorded dispatch time or is at least 15 minutes old | Investigate possible in-flight effects; age alone never authorizes retry |

Unknown outcomes are critical; other signals are warnings. Persisted `renewal_uncertain` takes precedence over the generic provider-error warning, so rotating-token uncertainty retains its critical no-retry action. Provider-error codes and payloads are never included in this report. Counts represent their
own evidence source and must not be summed into a count of unique incidents. The
same incident can appear in both an action and a publication step. No currency
amounts, customer/account/resource identifiers, raw errors, opaque grants, request
payloads or customer text leave this endpoint. It never asserts that paused or
unknown publication resources did not spend.

## Durable Provider Coordinator Evidence

The original PR137 observed legacy simulation publication tables only; production
coordinator uncertainty was unobserved until this extension. The endpoint now also
reads the frozen coordinator's scalar execution-step, original-attempt, exposure
reservation and ledger fields. It never parses request/receipt JSON to guess state.

`provider_held_exposure` separately reports observed held counts and oldest ledger
period end for `contract_test` and `live`. Held exposure can be legitimate for a
paused graph awaiting activation, so held alone is not an alert. Counts are not
money and are never combined across currencies. Existing legacy signals have a null
`environment`; new coordinator signals explicitly name their environment.

| Code | Evidence | Meaning |
| --- | --- | --- |
| `provider_creation_unknown` | Current step is `unknown` or `conflict` | Critical; preserve original attempt and reservation, reconcile without retry |
| `provider_creation_no_effect` | Current step is `verified_no_effect` | Warning requiring review; does not grant permission to replay or release exposure |
| `provider_dispatch_overdue` | Current step is `dispatching`/`emitting` and original attempt is at least 15 minutes old, or has no attempt timestamp | Critical; do not reclaim the attempt based on age |
| `provider_exposure_period_ended` | Reservation remains `held` at or after its ledger's end | Warning; period expiry is not settlement evidence |

Step state is the coordinator's current projection of the latest immutable receipt
for its unique original attempt. A later unknown/conflict supersedes earlier success.
Cancellation and closing workspaces do not suppress these signals, and a canceled
run is not treated as proof of no effect. The original attempt's timestamp indicates
dispatch age, not the timestamp when a later unknown receipt appeared. Reservations
remain held through paused creation, unknown effects, cancellation and expiry;
settlement is outside this endpoint. This package does not enable live execution.

Two additional bounded queries cover held reservations and current relevant steps.
They use workspace-bound joins and separate environments, and share the existing
500-row caps, truncation/lower-bound flags and PostgreSQL timeout. Up to 21 fixed
code/environment signals and two exposure summaries can be emitted. A capped sample
cannot establish absence of uncertainty outside its rows.

## Bounds And Gaps

There are eleven fixed read queries, each materializing at most 501 scalar-only rows;
500 are evaluated and the extra row detects truncation. PostgreSQL requests also
set a transaction-local two-second statement timeout. The request session closes
without committing. Timeout/database failures use the existing sanitized 503
response, never an empty healthy report. SQLite is offline test coverage, not a
production query-time guarantee.

Jobs use a recent sample ordered by start time/id; the first row for each exact job
identity is its latest sampled run. Other sources have deterministic ordering.
`evidence_truncated` and `counts_are_lower_bounds` explicitly mark incomplete
sampling. A bounded response is not a complete audit. Operators must inspect
scoped existing tools when truncated, and load/index qualification remains a
release gate. There is no query parameter allowing callers to expand the cap.

`no_attention_observed` means only that these sampled persisted states produced no
signal. It is deliberately not a global healthy state. The response always exposes
observation gaps: storage failures have no durable record; scheduler heartbeats and
never-started work are not observed; analysis rows use bounded persisted-state
observations rather than heartbeats; publication steps lack an independent age field; external alert delivery is
not configured. No storage call is made merely to manufacture a health result.

An approved monitoring system can consume fixed code/severity/count transitions
and route operators to this runbook without retaining customer payloads. Provisioning,
alert destination/escalation policy, incident delivery tests, deployed load thresholds
and actual storage/provider availability remain separate owner/release work. This
package neither provisions that system nor claims alerts have been delivered.

## Offline Validation

Deterministic SQLite/PostgreSQL tests cover recovered historical failures, stale
running jobs, future backoff and exact overdue boundaries, terminal renewal
uncertainty, preserved unknown reservations after closure, bounded/truncated
queries, sanitized database failures and the no-store operator response. The assembled
route matrix includes this route and denies real customer sessions before database
access under production and local-development settings.

The coordinator extension also verifies actual mocked Google creation: lost-response
unknown → verified same-attempt receipt → later unknown, including cancellation and
workspace closure. It tests dispatch/emission threshold boundaries, verified-no-effect
review, separate live/contract-test held counts, ledger-end warnings, truncation and
unchanged reservation state. No real provider calls or production grants are involved.
