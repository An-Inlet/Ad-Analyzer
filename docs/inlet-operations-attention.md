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
| `job_running_overdue` | Latest sampled running job began at least 15 minutes ago | Inspect worker ownership and progress before deciding recovery |
| `billing_event_overdue` | Active-workspace pending event has no future retry, and receipt/retry due time is at least 15 minutes old | Inspect webhook reconciliation; never infer payment from browser return |
| `billing_snapshot_overdue` | Active subscription lacks recent verification and any scheduled retry is at least 15 minutes overdue | Inspect reconciliation availability; do not grant entitlements manually |
| `connection_reconnect_required` | Active-workspace native/source connection requires a new grant | Direct the authorized customer to reconnect |
| `connection_retry_overdue` | Persisted connection error has a retry due at least 15 minutes ago | Inspect pacing/worker state; respect account-wide cooldown |
| `renewal_outcome_unknown` | Persisted renewal uncertainty | Preserve encrypted evidence; do not replay a possibly consumed rotating refresh token |
| `publication_outcome_unknown` | Publication step is unknown/conflicting, including closing workspaces | Preserve reservations and reconcile verified provider evidence; never blindly republish |
| `action_outcome_unknown` | Mandate action outcome is unknown, including closing workspaces | Preserve reservation; investigate current authority and receipts |
| `action_dispatch_overdue` | Dispatching action has no recorded dispatch time or is at least 15 minutes old | Investigate possible in-flight effects; age alone never authorizes retry |

Unknown outcomes are critical; other signals are warnings. Counts represent their
own evidence source and must not be summed into a count of unique incidents. The
same incident can appear in both an action and a publication step. No currency
amounts, customer/account/resource identifiers, raw errors, opaque grants, request
payloads or customer text leave this endpoint. It never asserts that paused or
unknown publication resources did not spend.

## Bounds And Gaps

There are nine fixed read queries, each materializing at most 501 scalar-only rows;
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
never-started work are not observed; local AnalysisRun history is outside this v1
signal; publication steps lack an independent age field; external alert delivery is
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
