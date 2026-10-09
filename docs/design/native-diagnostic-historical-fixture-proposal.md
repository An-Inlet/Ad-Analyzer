# Native Diagnostic Historical Fixture Proposal

Status: proposal only; parent review required before producer implementation.
Base: `868a740`. Branch: `codex/native-diagnostic-historical-investigation`.

## Confirmed Single-Case Failure

Ran exactly once, using the local venv:

```sh
python -m pytest 'tests/test_native_diagnostic_assembly.py::test_current_owned_vault_assembly[sqlite-None-google_ads]' -q --tb=long --junitxml=/workspace/inlet-evidence/20261009/native-diagnostic-investigation/sqlite.xml
```

Exit 1. JUnit: one failure, zero errors/skips, 3.883 seconds. Raw artifacts:
`/workspace/inlet-evidence/20261009/native-diagnostic-investigation/sqlite.{log,xml,exit}`.
The exact path is native diagnostic `seed:45` -> durable optimization `ready`
-> provider execution mandates `setup` -> provider qualification `seeded`
-> Google action plans `setup` -> test mandates `seed:86` -> current mandates
`approve:180` -> `AdvertisingWritesDisabled` (409). No native read assertion was
reached. No other test case or PostgreSQL command ran; this is not module qualification.

## Existing Producer And Schema Boundaries

`tests.retired_snapshot.PIN` remains
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`. `extract` verifies the exact local
ancestor and pinned app/tests tree hashes; it does not fetch or modify a checkout.
`run_bounded` gives the existing fixture subprocess 180 seconds and 16 MiB output.
The driver asserts that imported app code belongs to the extracted snapshot.

Existing `retained_review_fixture` produces a preview/review/run/receipt with one
MockHTTP write. `retained_initial_rule_fixture` produces a Meta initial Start
and candidate with zero writes. Neither supplies the minimal three-provider
mandate/source graph needed here. Do not reuse these modes by discarding their
extra effects or pretending their Meta-only graph covers every provider.

Existing SQLite seam creates a separate file-backed `current.sqlite` with CURRENT
Base metadata and foreign keys enabled, then gives its URL to the child. This is
current compatible schema with historical record production, not historical
migration replay. PostgreSQL uses only the caller-owned disposable schema named
`inlet_test_<32hex>` (or the existing migration-fixture pattern), verifies search_path,
and requires explicit disposable configuration. The parent fixture owns schema
cleanup. No public reset, migration, aggregate database, or frozen W1 change.

## Proposed Narrow Shared Interface

Add to `tests.retired_producer_fixture`:

```python
@dataclass(frozen=True)
class RetainedNativeDiagnosticIds:
    workspace_id: int
    actor_id: str
    account_id: int
    mandate_id: str
    revision: int
    consent_id: str
    policy_digest: str
    ledger_id: str
    environment: str
    provider_posts: int

@contextmanager
def retained_native_diagnostic_fixture(
    customer_engine: Engine,
    artifacts: Path,
    provider: Literal["google_ads", "meta_ads", "tiktok_ads"],
) -> Iterator[tuple[Engine, RetainedNativeDiagnosticIds]]: ...
```

Extend only the existing private fixture/driver dispatch with a closed
`native_diagnostic` mode and a required closed provider argument for this mode;
existing mode signatures/behavior stay unchanged. In the pinned interpreter call
its genuine `tests.test_durable_optimization.ready` with that provider. That helper
creates owned source/goal plus genuine approved simulation mandate and provider
mandate/consent; it returns before optimization preparation, approval, run, claim,
or execution. Commit those records and return scalar IDs and the exact returned
binding fields, never credentials, payloads, runtime objects or qualification
objects. Assert zero server posts/writes and zero provider attempts/responses/
receipts/reservations. If the current schema rejects pinned writes, stop and report
compatibility rather than altering constraints or fabricating rows.

In the CURRENT interpreter, load the returned scoped mandate/consent/ledger/account
and verify every returned binding field against those persisted records. Construct
the existing typed binding from this verified result, without calling consent
again. Keep current native diagnostic request and collector implementation. The
existing synthetic vault resealing, real current principal/session and post-HTTP
source/role/account/OAuth/session checks remain current. No capability monkeypatch,
environment write toggle, blanket historical marker, invented consent or relaxed
mandate-negative assertion. Verify current capability still raises before reads.

Adapt only this module's setup to hold the fixture context through each DB/HTTP
assertion and use its returned engine (important for SQLite's separate file).
The pure Google expiry-parser case needs no historical fixture. Preserve provider
matrix and invalid mandate revision 999, foreign account, currency, expired grant,
wrong-vault-context and no-inventory-HTTP assertions unchanged.

## Qualification After Approval

Run the targeted repaired SQLite case first, then this module's existing SQLite
and disposable PostgreSQL matrices, with actual fixed MockHTTP collectors. Assert
zero mutation requests and no added execution graph, including after negative
cases. Check existing producer modes with their bounded relevant compatibility
cases if shared dispatch changes. Run Ruff, bare mypy and diff checks. Record any
failure without widening historical authority into current behavior. No Full or
live provider calls. No producer code was implemented in this investigation.
