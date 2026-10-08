# Exact Catalog Receipt Helpers — Offline Qualification

Branch: `codex/inlet-catalog-receipt-helpers`, based on root `5ec904c`.
Actual model dependency `e512a10` and schema/trigger dependency `c7ce328` were
cherry-picked as `baa261e` and `4796770`. Historical validator interface addendum
is `a790fea`. No runtime route/service/evidence-reader wiring belongs to this package.

## Implemented

`app/planning_documents/catalog_receipts.py` provides the reviewed strict receipt
payload/binding types, writer, submitted-selector resolver, atomic input-link helper,
saved-input catalog resolver, final saved-receipt recheck and bounded cleanup helper.
It validates actual owned native request/advertiser/source/currency/timezone, original
session and authentication epoch, privacy, complete target indices, canonical payload
and exact input bindings. Exclusion-only inputs recover their original selected snapshot
from private revision/account links. New use preserves original expiry; target lookup
never rereads native providers or remaps canonical IDs to another observation.

The two separately reviewed historical validators reconstruct complete payload/selector/
input-link integrity without original-session-active or original-TTL requirements.
Current read/privacy authorization remains the export caller's responsibility. New-use
helpers layer current owned DB authorization, source/session/expiry checks over those
same structural checks. All helpers are DB-only; none commits, rolls back, performs
identity IO or calls a provider. Caller final authority checks after all waits remain
required. Cleanup requires its own caller-authorized, caller-committed maintenance
transaction; the helper performs one bounded batch and preserves linked history.

## Checks Actually Run

* Initial actual SQLite/PostgreSQL helper cohort: 50 passed.
* Affected helper + actual storage/migration + model contracts: **54 passed in 76.11s**,
  measured process wall time 80.302s, exit 0. One existing Alembic path_separator
  deprecation warning. No skips. Raw: `final.log`.
* Final typed integrity-error hardening: **20 passed, 30 deselected in 38.99s**, covering
  all three providers' actual saved exclusions/fixed/scenario selections and malformed
  payload/source correspondence on both DBs. Raw: `final-binding.log`.
* Actual persisted Meta connection-generation and advertising-account currency drift:
  **4 passed, 50 deselected in 6.05s**, recorded in `final-source-race.log`.
* Final root integration compatibility repair: no-target saved inputs may be generated
  by a different current owner; target-bearing inputs still require original receipt
  identity. **22 passed, 36 deselected in 41.30s**, actual second-owner bothDB cases plus
  all-three-provider saved-selection paths. Raw: `final-owner.log`.
* Whole Ruff and full configured mypy (1059 source files), plus `git diff --check`.

Evidence directory: `/workspace/inlet-evidence/20261008/catalog-receipt-helpers/`.
Tests use real registered SQLAlchemy models, immutable triggers and disposable isolated
PostgreSQL schemas; native observations come from real collector paths using MockHTTP.
No invented receipt tables, live provider calls, advertising writes, resets, hosted CI
or Full suite. The maintenance test explicitly injects a future cleanup clock and a
lower test-only quota to prove separately committed cleanup survives actual later
capacity denial; this is functional transaction evidence, not a production timing test.

## Remaining Integration

Root must wire separately authorized maintenance before V2 IO, final receipt persistence,
input atomic links and generation saved-catalog/final rechecks. Storage lane completes
DB-aware archive/export using the historical validators. Customer browser acceptance
and parent service idempotency/fresh-authority/cleanup races remain integration checks;
this helper package does not claim those routes are working or deployed. Original native
TTL may constrain interactive use; no deadline or production lifetime was changed.
Independent review required before integration.
