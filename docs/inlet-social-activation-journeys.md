# Persisted Social Activation Journeys

This dependent test package starts from frozen activation coordinator
`dd71cdd1ea1413752001d32e016dcb6635cdedde`. Shared coordinator, schemas, migrations
and provider adapters are unchanged.

Both Meta and TikTok journeys create their complete paused graphs through real
private-media validation, B14 source approval, separately consented production
mandate records, concrete HTTP serializers and persisted creation receipts. They
then prepare a distinct activation review. Creating an activation run without exact
separate approval is rejected. The tests approve that review, claim and emit each
actual status-only adapter request, and read the owned normalized receipts.
Campaign activation is last; verified target state does not imply delivery time.

Creation and activation retain exactly the same reservation ID and amount. The
server-only contract-test exposure reader explicitly excludes this parent's held
reservation from the other-reservations component, while keeping its proposed
exposure amount. It never creates a second budget pool or treats activation as new
spending permission. These callbacks are contract scenarios, not native/live
qualification, and they do not bypass source_current, DB consent or authority.

A lost acknowledgement with delayed provider state remains unknown. A later exact
readback resolves the original attempt/fence, appends a superseding receipt and
never emits a replacement update. Duplicate execution and foreign-workspace receipt
access are rejected. The reservation stays held after both verified activation and
uncertain outcomes.

After a durable claim, external changes to the Meta creative body or TikTok cover
metadata prevent activation through the full-graph preflight. Cancellation, native
connection deletion and connection-generation changes likewise prevent emission.
Those scenarios retain the original parent reservation.

The tests use real generated MP4/PNG bytes and MockTransport provider responses on
disposable SQLite/PostgreSQL. They are offline behavioral verification, not live
account eligibility, native exposure qualification, delivery or production readiness.
Default factories remain disabled. No live credentials, provider calls, spending,
merging or deployment occurs.

Fresh resumed validation with disposable PostgreSQL enabled:
`pytest -xra tests/test_social_activation_journeys.py` completed with **24 passed,
zero skips**, in 157.40 seconds. Log:
`/tmp/inlet-social-activation-journeys-resumed.log`. The earlier interrupted run is
not pass evidence. Whole-tree Ruff, configured mypy (389 files) and diff check passed.
The only prior-helper adjustment converts PostgreSQL's exact SUM(bigint) Decimal
result to int before strict exposure validation; no authority or amount is changed.
Full and hosted CI are not verified for this candidate. No workflow dispatch was
attempted while that operation remained paused.
