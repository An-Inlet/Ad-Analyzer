# Genuine Historical Producer With Current Lifecycle — Feasibility

Base `da4cd74`. Test-only seam; no application or advertising capability changes.

`tests.retired_producer_fixture.retained_review_fixture(customer_engine, artifacts)`
is a context manager yielding `(current_engine, RetainedReviewIds)` with workspace,
preview, review, actor, run, attempt and reservation IDs plus the observed synthetic
provider POST count. No runtime, cached authority or credentials cross the process
boundary. PostgreSQL uses only the supplied `inlet_test_<uuid>` schema. SQLite uses
a dedicated file database with current metadata and foreign keys enabled on both
processes; it does not replace or reset the caller's in-memory database. The yielded
engine must be used for current assertions. No current DB state is overwritten.

The driver imports untouched historical fixture/runtime code from verified local
commit `2155ff3e3ab00cd62057dd86cb49d45359d4f49f`, app tree
`6507ee4da861c63ebbc9ce0210c558c0de19d873`, tests tree
`06cc6a9ecb7466c3e94a5bd6558ea73befbbe4cc`. It verifies the actual imported app path.
It performs real historical consent→preview→review→approval→claim→one MockHTTP
provider effect against CURRENT tables. It does not insert fabricated approval or
mandate rows. The historical process terminates before current assertions begin.
Shared extraction utility uses local ancestor objects only, no network fetch,
bounded execution/logs and process-group termination on timeout.

Current unpatched code then verifies exact owned export and foreign-workspace
isolation, rejects a new claim through the immutable planning write guard, erases
derived observations/previews, and preserves the original review/attempt/held
reservation and immutable provenance fields. The four nullable preview-link fields
are required to retract, rather than incorrectly asserted unchanged. Fresh Sessions
read the post-erasure state.

Qualification: initial producer succeeded on both databases, but fixture assertions
failed because the custom SQLite engine omitted FK activation and because full
export-row equality ignored legitimate link nulling. Those fixture defects were
fixed; no product guard or lifecycle logic changed. Corrected proof **2 passed in
27.49s**. Reusable interface qualification **2 passed in47.06s** with both SQLite and
PostgreSQL. Raw final log/JUnit copied to
`/workspace/inlet-evidence/20261008/retired-compatibility/seed-final.{log,xml}`.
The unchanged extraction/process utility was then factored into
`tests/retired_snapshot.py` for independent reuse; no semantics changed.

This proves feasibility, not adaptation of every dependent lifecycle/restore suite.
Consumers must retain current export/privacy/schema/restore assertions and exact
original provenance; historical forward behavior remains separately archived.
No Full, live request, shared schema reset, deployment or activation ran.
