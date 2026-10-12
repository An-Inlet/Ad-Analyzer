# Q13 V6 Customer Report And Historical Retraction

Test-only package based on bcc362a. Own one new test module and package ledger;
no production, fixture-default, retention, policy, schema or browser changes.
Use configured_owner_review, actual authenticated create/edit/generate/assertions/
events/version/export/request-result APIs and original session. No seeded plans,
clock changes, producer substitutions or new observed-status records.

## Exact Lifecycle

One function, SQLite and PostgreSQL (two nodes). Generate genuine V6 V1, select
its investigation-only owner action, and record a customer claim describing
completion of manual investigation, not application of a native budget change.
The resulting ManualAssertion remains customer_report_only. Replay the exact
request and query its assert_applied receipt: identical event and sequence, no
new rows. Changed statement under the same request key must return 409 with
`request key is bound to different input` and no graph delta.

Edit only the milestone using expected input revision 1 and version 1, then
actually generate V2. No report/event is carried into a new action. A new report
against V1 at the current event sequence must return 409 with
`plan version or event sequence changed`. Retraction of that original report
against V1 with a wrong supersedes ID must return 409 with
`event chain head changed`. All refusals leave planning rows unchanged.

The correct retraction references the actual original event ID, exact original
version/document/action digests and current event sequence. It appends sequence
2 while version/input heads stay 2. It preserves original actor identity,
monotonic recorded timestamps and customer_report_only verification, has null
reported_applied_at, and never asserts provider observation, application or lift.
Exact replay and request-result lookup return the same event without writes.
A distinct request trying to retract the already retracted head must return 409
`manual report already retracted`, with no graph delta. Original report request
replay still returns its original sequence/event after V2 and retraction.

Read exact ordered events, original V1 and current V2, and readable exports for
both. Both document payloads/digests and retained input/version/dependency rows
remain unchanged during the event-only stages; only expected append-only event,
request-receipt and plan event-sequence changes are allowed. Actor matches the
actual fixture owner; session equality is checked as a boolean, not raw operands.
Snapshot both MockHTTP call lists around each event/read/export phase; generation
may make approved mocked reads, so restart the baseline after V2 generation.
Financial/execution counts remain unchanged throughout. Preserve safe synthetic
documents/events/exports only; no cookies, request headers or credentials.

## Qualification Boundary

Source review precedes execution. Prepare exact two-node collection and immutable
source/runner/resource manifest after parent slot approval; SQLite then PostgreSQL,
stop first unexpected failure, no retry. Whole Ruff/configured no-path mypy apply.
No tests or heavy checks are authorized by this document itself.

This tests an existing whole-system branch distinct from Q12's obsolete-decision
refusal. Existing legacy service tests already cover historical withdrawal; this
adds actual V6 HTTP/owner-proof joins. It does not implement the missing independent
provider observation producer, establish elapsed TTL expiry, complete Q13/Q16,
resolve reconnect retention, assess human quality or explain prior timing failures.
