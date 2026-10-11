# Owned Creative Paired Reader — 2026-10-11

Base `1f1ae748a03b9c66325e86ed9b96955047d3b42f` implements the approved
[combined-reader interface](design/owned-creative-paired-reader-interface-v1.md).

New port: `OwnedCreativePairedReader(sessions, *, principal, provider, policy,
store, clock).collect(ticket) -> CreativePairedEvidenceV1`.

The original principal is snapshotted. Complete canonical v5 policy/ticket, explicit
selected/creative input and original actor/session checks precede provider/storage
work. Existing owned paired-reporting and pinned-image readers receive the same
actual ticket and original authority. No fields are stripped or retagged.

A fresh final PlanningReadContexts transaction performs selected/image/selected
rechecks. The returned SQL creative proof must equal the proof derived from actual
private collection. Context exit revalidates original authority. After DTO checks,
a final strict aware UTC clock sample must not precede ticket preparation, collection
or original observations and must be strictly before all original reference expiries.
No deadline or image observation time is renewed. No blanket callback-error handler.

Only the new reader and tests/docs are added. No service, capability, repository,
history, UI, persistence or default change. A ticket is not proof of the current
saved-input SQL head. Future atomic persistence must repeat both rechecks with the
saved revision, version, privacy and CAS bindings. Fixture success is not customer
v5 API generation, live media qualification or completed frozen Q03/Q04 acceptance.

## Qualification

Evidence: `/workspace/inlet-evidence/20261011/owned-creative-paired-reader/`.
Tests exercise actual uploaded local image bytes, confirmed goal, original customer
session, fixture billing and provider-backed native MockHTTP. Google additionally
uses actual range and selected-capture APIs; social reporting retains unsupported
selected-event gaps. Session instrumentation rejects provider/storage I/O under SQL.
No ready reporting/image envelopes replace production collection.

Initial positive SQLite cohort:4passed, zero skips (`positive-sqlite.xml`).
Initial static failures were only test annotations and a loop name shadowing an
import; failed logs retained. Final results:

- Main both-database cohort:32passed, zero skips,201.044seconds (`both-db.xml`).
- Additional final-proof/second-reporting-check, callback and requested-hash cases:
  10passed, zero skips,37.863seconds (`final-boundaries.xml`).
- Cases include reporting mutation during image reads, image mutation after inspection,
  session/membership/goal/payment/privacy changes, wrong policy/original session before
  I/O, explicit empty input, final-context exit expiry/backwards/naive clock and exact
  callback exception propagation. Deliberately injected SQL mutation after the creative
  recheck is rejected by the second reporting recheck and rolled back.
- Actual successful collection and denied attempts leave planning rows/input/version/
  request counts unchanged. Native image/reporting observations are not relabeled.
- Whole Ruff and configured no-path mypy passed (1,395 source files); diff check passed.
  No production test failure occurred.

No production providers, external calls, PostgreSQL reset, aggregate/Full, remote
push, hosted checks, merge, deployment or runtime activation.
