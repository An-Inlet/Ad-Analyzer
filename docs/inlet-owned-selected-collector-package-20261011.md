# Standalone owned selected collector — 2026-10-11

Base `ce6b01a`; current proof port review closed before this work. Adds only
`selected_plan_adapter.py`, `selected_plan_local.py`, dedicated tests and this ledger.
No policy registry, service/generation route, retained-source dispatch, schema,
transport default, public v4 availability or advertising mutation is enabled.

## Concrete ports

- `OwnedSelectedEvidenceReader(sessions, *, principal, provider, policy, clock)`;
  `collect(ticket) -> SelectedPlanEvidenceBundleV1`.
- `check_selected_start(db, *, principal, ticket, authorize, clock)`.
- `capture_selected_proof(db, *, principal, ticket, authorize, clock)` returns the
  complete ordered `SelectedRetainedProofV1`.
- `recheck_selected_sources(db, *, principal, ticket, bundle, authorize, clock)`
  performs only SQL/local validation; caller owns transaction and external fact.

Generation requires the exact reserved canonical v4 policy/digest and explicit
selectors. Every SQL block uses the original principal through PlanningReadContexts;
identity refresh occurs outside SQL. Native catalog and metadata acquisition uses
existing real collectors with explicitly injected MockHTTP in tests. Saved catalog
receipts use the existing shared resolver without changing old behavior.

Only the recognized >366-day native window becomes an inventory gap. Authentication,
transport, parser, source and integrity failures abort. At least one actual catalog
is required for the evidence deadline. Explicit selected captures never fall back
to latest or silently become gaps. Complete snapshots and their exact original pins
are retained even for accounts without catalogs. Whole captures are bounded by
32 MiB; account/campaign/window output is bounded by 400 slots. Projection uses one
prepared whole-graph index per account, not a full capture parse per window.

Selected performance references bind exact original acquisition times, source,
privacy, key/schema/digest and catalog deadline. Missing cells remain unknown;
observed zero and positive Decimal values remain distinct. Actual commerce goal
progress and exact input/policy context retain conservative V3 semantics. Final
reconstruction rechecks current proof, every selected graph, actual account catalog
units, saved receipts, commerce and deadlines, then entitlement and authority.
All selected contexts/listeners close before returning or caller persistence.

## Validation boundaries and retained failures

Evidence root: `/workspace/inlet-evidence/20261011/selected-plan-collector`.
All pytest invocations have distinct scratch basetemp, durable JUnit/run logs and
`--durations=20`; original failures were preserved.

- `sqlite01`: four failures exposed the reused fixture's disabled SQLite FK pragma;
  enabled actual FK enforcement before source construction. One no-selection passed.
- `sqlite02`: three passed; two assertions mistakenly compared typed Decimal to string.
  Corrected expected Decimal; no implementation or arithmetic weakening.
- `sqlite03`: ten passed; saved-receipt setup tried public v4 plan creation and got
  the correct 409. Replaced that setup with the real internal prepare/resolve,
  owner identity fact, repository writer and catalog receipt binder. Public v4
  remains disabled. `sqlite04` saved-receipt test passed.
- `sqlite05`: one passed; two negatives correctly aborted with GoogleReadError rather
  than the narrower expected native error. Expected fixed provider error type added.
- `sqlite06`: three passed; synthetic partial-catalog test incorrectly treated a
  projected catalog as full native inventory. Switched to a labeled closed native
  fixture. `sqlite07` caught its wrong timezone; `sqlite08` caught units assigned to
  the wrong fixture model level. Request units fixed exactly; `sqlite09` passed.
- Whole Ruff and mypy (`static08`, 1340 source files) passed before final DB cohort.

Actual positive fixture: confirmed owned goal and actual normalized Shopify import,
Google source/aggregate bootstrap from the existing planning fixture, real selected
options/confirmation/capture API through encrypted Vault/OAuth/read MockHTTP, then
actual standalone owned collector/native metadata HTTP and final SQL reconstruction.
No selected captures or ready evidence bundles are seeded. Source bootstrap rows
remain the explicitly inherited fixture boundary; this is not a zero-user/live demo.

The partial-catalog final-reconstruction test uses a **synthetic catalog for a second
owned SQL source** plus the first account's actual API-acquired selected graph. It
proves preservation and denial after graph deletion, not an ordinary endpoint that
emits a >366-day saved catalog. The real all-unsupported-window collector abort is
separately tested, rather than inventing another permissible error-to-gap catch.

Final DB outcome and immutable head are reported in the handoff. No Full, hosted,
remote, production provider, database reset or deployment was run.

Final `both10`: **30 passed, zero skips/failures, 99.56s** on SQLite and disposable
PostgreSQL unique schemas. Includes actual positive/zero/missing/explicit absence,
real saved receipt reuse, callback revocation, source/head/capture/deadline denial,
identity and native HTTP outside SQL, transport/parser aborts, all-unsupported-window
abort and the labeled partial-catalog graph reconstruction/deletion test.
`static08/fresh-import.log` confirms fresh-process imports of both new modules;
`ruff-final2.log`, `mypy-final.log`, and `diff-final.log` are clean. PG slot released.
