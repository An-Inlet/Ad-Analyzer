# Contention Evidence And Independent Gates

The owner explicitly authorized continuing after the unresolved same-key PostgreSQL
failure: verify failure-safe evidence collection before another contention run, and
partition the 47 configured cases so independent acceptance can proceed. Overall v6
qualification remains withheld. No product authority or deadline changes are allowed.

## Failure-Safe Contention Recorder

The test-only recorder surrounds the existing contention harness. Each client worker
sets a test-local ContextVar; actual synchronous ASGI worker propagation must pass a
focused test before use. Every request has a fixed outcome slot, initially not started.
HTTP responses retain only status and fixed allowlisted categories; exceptions retain
only a Boolean/state, never exception text, payloads or identity attributes.

Record relative monotonic start/end timestamps, thread CPU and duration for preparation,
its pre-refresh gates, identity refresh, final save setup/save, every authority-lock
call, fresh-source recheck, retained-source capture, storage and version decoding.
Every authority final guard records before/after age against its original unchanged
fact, an invocation-local ordinal, final-fact Boolean, fixed phase and exception state.
Fact objects stay private and are never serialized. Native expiry and route-conflict
events have separate exact schemas, types and vocabulary. Additional fields are
rejected; the route-conflict schema does not broaden the expiry schema. No SQL, backend IDs, user/session/account
IDs, document text or request content is written.

The winner's coordinator is measured separately, including loser-entry waiting and
observer engine creation, connection, polling, disconnection and disposal. An exact
PostgreSQL blocker relation is retained only as a Boolean timestamp. Authority-lock
spans include lock acquisition plus the existing authorization SQL; they are not an
exclusive server wait metric. All timings overlap; do not subtract coordinator or
instrumentation time from authority age to manufacture an acceptance result.

A test-local sampler retains bounded shared cgroup numeric counters every 250ms,
plus before/after samples and sampling duration. These reflect the shared execution
scope, not per-request resource attribution. Event/sample overflow or observer errors
invalidate successful evidence. No clocks, facts, guards or application checks change.

The outer context persists evidence after the thread-pool context has joined both
workers, even if a future or a final assertion failed. An evidence-write failure
must not replace the original exception; emit only a fixed error marker. Successful
runs also require observers restored and sampler/workers closed. The original
acceptance checks remain; the new evidence is not a substitute for them.

## Harness Deadline Risk

The second preparation waits for the winner's acquired lock before returning to its
own final refresh. Therefore the winner's final authority age includes the loser's
provider refresh and save setup, up to one second of event waiting, plus observer
connection and polling while the winner holds its transaction. This test coordination
can consume material deadline budget. It does not intentionally require a five-second
hold, but its maximum bounded overhead plus real work can exceed five seconds.
The original failed winner's phase is unknown; the risk is not historical causation.
Measure the unchanged sequencing first. Any later coordinator redesign is a harness
change, not an application repair, and needs separate review and evidence.

## Independent Configured Partition

The original exact 47-node list remains immutable in the evidence root. None depends
on same-key concurrency output or a passing concurrency assertion. Independent
function-scoped database, application overrides and monkeypatch fixtures isolate them.

- 19 component cases: 16 selectors/configuration defenses and three retained readers.
- 14 SQLite serial cases: ten configured v6 owner cases, one deliberate pre-save
  expiry case, and one journey each for default v3, Google v4 and creative v5.
- 14 PostgreSQL serial counterparts.

These cases still exercise changed v6 source/revalidation behavior and can independently
fail. Freeze exact source and nodes before execution; run static gates and components,
then SQLite before PostgreSQL. Stop each partition at its first unexpected failure;
retain all original results/unrun identities. Crossing to another independent partition
after a failure requires an explicit disposition/review rather than pretending the
prior gate passed. No skips, weaker assertions, unchanged retry-to-green, or overall
qualification based on serial passes. Preserve the prior 59 acceptance passes and one
unresolved concurrency failure separately from this new configured coverage.
