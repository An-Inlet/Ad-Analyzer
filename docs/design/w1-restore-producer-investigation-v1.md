# W1 Restore Producer Investigation — Not An Implementation Freeze

Read-only on d665feb. The21 frozen restore failures enter current
`scripts/inlet_restore_drill.seed → inlet_restore_fixture.seed_financial →
execution_mandates.consent`; terminal immutable advertising-write denial masks
later behavior. Breakdown: three native restore cases, ten populated graph/tamper,
four performance/tamper and four initial document/privacy cases. No test run here.

A seed-only replacement is insufficient. Current `verify_populated` explicitly
expects `optimization.claim_step` to return None, then execute_claim and repeat
preparation to raise historical state-specific409s. Current immutable denial now
raises earlier. Preserve current ownership/receipt/held amount/high-water/action
count/approval/digest/export/foreign isolation checks, but future bounded repair
must assert current AdvertisingWritesDisabled for those three forward operations,
with no provider calls or changed graph. Settlement refusal remains its actual
current behavior and must not be replaced. No blanket verifier guard bypass.

Potential seam: verified pinned child runs original `inlet_restore_drill.seed`
against parent-owned current disposable schema; parent retains all current
fingerprint/constraint/ownership/privacy/performance checks and actual pg_dump /
pg_restore plus sentinel cleanup. Whole native drill currently calls seed itself,
so inject a closed test-only seed callback at that exact seam or a scoped test
monkeypatch replacing only drill.seed; never historicalize run_drill/verifiers or
invoke the pinned native restore command. Need separate interface approval.

The pinned archive already contains scripts, but extraction presently verifies
explicit app/tests tree hashes only. Before using script producers add exact
scripts tree verification:2155ff3:scripts =
`c49d7769faa20df001536e6f819a1e1f7c860c57`. Inspection found no diff from pin in
inlet_restore_drill.py, inlet_restore_fixture.py or inlet_restore_initial_fixture.py;
the runtime imports, rather than script bytes, introduce the current denial.

Closed restore mode would require empty synthetic target graph, exact fixture
workspace IDs901/902, no preexisting user data, and narrowly approved prefixes:
inlet_test_UUID for ordinary PG fixture, inlet_restore_UUID only for native drill.
SQLite in-memory fixtures cannot cross interpreter; use the established separate
file-backed current-metadata test engine while preserving current assertions.
Native parent owns migrations, schema creation/drop and restore. Child no DDL;
only bounded scalar IDs/counts and verified fixture digests return after commit.
No external archive, provider network or ad writes outside MockHTTP.

Remaining feasibility risks: current extra schema constraints may reject pinned
seed; initial graph mappings and complete table/row fingerprints must be read
back under current code; actual native backup still must preserve current trigger
DDL. The21 cases are not fixed by this investigation. Freeze a separate bounded
seed/verifier-interface package after migration profiles; do not add it silently
to those modes or weaken current CLI protections.
