# Current Closure With An Authentic Late Publication Receipt

Approved interface `6d3817b`, based on `eb96dcc`. Exactly two original failed
SQLite/PostgreSQL cases of `test_late_publication_receipt_is_strict_evidence_only`
are adapted; the other quiescing functions remain AST-identical.

The fixed original producer uses verified2155 source, calls actual approved,
claims once, persists the actual verified_no_effect receipt, claims the same first
step again with a new fence, and calls unchanged FixturePublicationTransport once.
Its actual typed verified_effect/PAUSED receipt remains unrecorded until current
closure. A strict <=16KiB data-only result contains scalar commitments and that
receipt; no historical authority, runtime or Session crosses. Current code reloads
and validates both requests, actual approved plan/action/mandate, first receipt,
second dispatching attempt and exact late receipt scope/fence/digest/time.

Current consumer retains original user/session construction, confirmed/quiesce,
grant erasure, late duplicate receipt recording, strict invalid-fence/conflict
rejections, dispatching step and blocked lifecycle assertions. New current
DatabaseFixtureAuthority only supplies the original signature; the final claim
hits the unconditional planning write guard. Its exact exception is explicitly
asserted and is not claimed to exercise deeper closure authorization.

Exact financial/publication snapshot comparison permits only mandate.paused=true,
action.cancel_requested=true and one strictly validated late receipt append. The
first receipt, plan, steps, revisions/audits, action state and all monetary counters
including the original reserved_micros remain unchanged. No provider-execution
rows are created. This is the original legacy horizon reservation, not a claimed
ProviderExposureReservation or financial-finality proof. No unexpected delta or
broader exemption was necessary.

Source storage rejects aliases and nonsymlink/regular-file violations before
factory/DDL, uses a new exclusive SQLite file or exact disposable loopback owned
PostgreSQL schema, and checks all tables empty/schema unchanged. The explicit
SourceLifetime profile retains source provenance and removes only reaped immutable
source copies, preserving media, IDs, logs and SQLite files.

## Qualification

Evidence: `/workspace/inlet-evidence/20261009/late-publication2/`.

- Initial exact two current cases: **2 passed**, zero skips/failures/errors,
  21.598 seconds (`probe.xml`).
- Pure parent/child URL/file/factory guards: **34 passed**, 3.312 seconds
  (`guards.xml`).
- Final whole quiescing +default boundaries+lifetime+guards: **150 passed**, zero
  skips/failures/errors, 32.656 seconds (`qualified.xml`). This includes14 quiescing
  cases (only2 new original failures),86 unchanged execution/transport boundaries,
  16 lifetime cases and34 guard cases.
- Whole Ruff passed (`ruff-final.log`), bare mypy passed1216 source files with own
  `/tmp/inlet-late-publication2-mypy-cache` (`mypy-initial.log`), diff check passed.
  Initial Ruff line-width findings before formatting are retained in
  `ruff-initial.log`; no pytest failure occurred. Command exits checked separately.
- `assertion-proof.json`: six original current assertions remain AST-identical;
  two original preclosure non-None assertions are preserved in the fixed child and
  current typed readback. Three exact planning-denial assertions were added.
  Every other function in the current quiescing module remains AST-identical.
- Both final actual source copies were verified removed after successful reap,
  33,716,830 logical bytes; original artifacts remain outside extraction.

Exact commands (local disposable PostgreSQL environment, evidence-local basetemp
and JUnit paths):

```text
pytest -q tests/test_customer_quiescing.py::test_late_publication_receipt_is_strict_evidence_only
pytest -q tests/test_late_publication_source_guards.py
pytest -q tests/test_customer_quiescing.py tests/test_planning_execution_boundary.py tests/test_planning_provider_transport_boundary.py tests/test_producer_source_lifetime.py tests/test_late_publication_source_guards.py
ruff check .
MYPY_CACHE_DIR=/tmp/inlet-late-publication2-mypy-cache mypy
```

No W1 mutation/aggregate rerun, new historical batch, live provider, blanket
retained-execution fixture or product capability change. Only the two exact
original identities receive closure credit after independent review.
