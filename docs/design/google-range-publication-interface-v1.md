# Owned Google Range Publication And Retained Receipt V1

Dependencies: original-session reporting service, injected strict raw range reader,
existing aggregate publication/manifest reader and workspace privacy lifecycle.
This additive read-only path must not change the ordinary seven-day scheduler or
old reporting V1/V2/V3 interpretation. Reserve migration0092 for one receipt table.

## One Explicit Acquisition

The public intent is account ID, request ID (32hex), inclusive local start/end dates.
Use one contiguous range covering primary and comparison windows, at most400 closed
days. A new original-session operation captures exact source/grant/account units,
privacy, current completion and every scheduling field. Pending cursor/staged pages
make acquisition unavailable. No source locks survive into external reads.

Acquire a complete `GoogleAggregateRangeV1` using the injected raw range adapter.
It must bind the original owned request and exact dates, have terminal pagination,
pass all bounds and preserve omitted rows. Required missing metric fields fail;
there is no normalized zero substitution. Its conversions remain generic aggregate
metrics, separate from customer-selected observations.

At final workspace/account/source locks, repeat original-session/paid/sync checks
and compare the exact initial source, current completion, scheduling and privacy
snapshot. A concurrent normal import/reconnect changes the snapshot and aborts.
Replace only actual campaign/day rows within the requested dates, upsert returned
owned campaign identities, and publish with the concrete range adapter descriptor.
Set source.last_sync_at to the exact completion time; retain every scheduler field
unchanged. Create a successful local job record for this actual acquisition, without
enqueueing unrelated analysis/execution. Read back the existing full manifest and
current completion before committing. Failure rolls back all row/pointer/job effects.

Calibration invalidation during publication may advance privacy. The resulting
completion and receipt use that final privacy, never a rewritten old selection.
Only privacy may differ from the initial scope as a result of that known transaction.
Final privacy must be greater than or equal to original privacy, with any advance
coming from the actual invalidation in this transaction, never an arbitrary restamp.
Fresh event confirmation after acquisition must use the actual resulting scope.

## Receipt0092

`google_reporting_range_receipts` is erasable workspace data, not financial history.
Fields: request ID primary key, workspace/account/integration IDs, completion ID,
job ID, initiating customer ID, canonical typed receipt JSON, payload digest and byte count.
Use composite account/workspace/integration and completion/account/workspace FKs,
customer and job/workspace FKs, immutable UPDATE refusal, and exact scalar/payload agreement. Canonical
receipt is bounded16KiB; no grants, session digests or raw provider bodies are stored.

Typed receipt commits schema/request ID, original initiating customer, requested
dates, original and final ReportingScopeV1, completion ID, manifest digest, concrete
query version, completed time, row count, acquisition result commitment and job ID.
Require original/final scopes equal except privacy, and final scope/completion
metadata exactly agree. The initiating actor is factual audit metadata; replay
still requires the currently authenticated original-session owner.
Validate the job's exact workspace/account/integration, Google platform, succeeded
state and dedicated `google_customer_range_read` type in addition to its FK. Compare
all completion fields including query, completion time, row count, dates, source
generation and units. The acquisition commitment is an audit hash, never a substitute
for actual acquired data and atomic publication proof.

Internal ports `store_range_receipt(db, receipt)` and
`read_range_receipt(db, workspace_id, account_id, request_id, require_current=True)`
do not authenticate sessions or commit. Current reads validate actual full aggregate
manifest/source/current pointer; historical export verifies immutable receipt and
completion metadata and labels history, never claiming old metric bodies are current.
Receipt deletion fences prepared exports and derived plans via existing privacy
revision; semantic workspace erasure removes receipts. Frozen0092 DDL must match
models on SQLite/PostgreSQL; refuse populated downgrade. Explicit lifecycle/export
registration and actual archive/erasure tests belong in the same package.

## Retained Replay

Under current owner authorization, same request ID plus same account/date body
returns its current retained receipt without HTTP. Different body or foreign ID
collision gives generic409. Stale current dependency gives409 without refetch.
Final publication checks for a concurrent receipt winner before touching any rows:
same semantic body plus current graph returns that winner; otherwise conflict.
Unknown-commit retry uses the same ID/body. Privacy erasure removes the receipt;
permanent deduplication is not promised. Never fabricate a receipt over an old
completion merely because its dates match.

No public/default live factory is enabled. Actual mocked HTTP, both databases and
customer API must prove the61-day request, atomicity, replay, scheduler preservation,
post-I/O races, archive/deletion and zero advertising-write requests before use by
selected captures or plan consumers. Later ordinary sync legitimately makes the
range stale; no independent range pointer, background session or scheduler pause
is introduced by this interface.
