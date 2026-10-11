# V6 Owner Review Retained Boundaries

Local implementation from e8c7600 under the reviewed slice-three interface.
This package does not register V6, alter defaults, implement service generation,
or authorize advertising changes. R01/R02 remain open; no diagnostic rerun or
performance claim is part of this package.

## Changes

Exact V6 current capture and recheck bind original authenticated input receipts,
complete canonical catalog tuples and retained owner review proof before and after
shared selected/reporting, commerce and creative current reads. Existing public
creative wrappers remain exact V5; private shared bodies handle the closed V5/V6
policy set. Recheck first validates the complete dependency set. Historical V6
validation checks the stored version and complete dependencies/pins before original
receipt/link/opaque owner commitments. It does not require current TTL, entitlement,
source state or media bytes. Original clean Session/Connection roots, read roles,
privacy/goal checks and final DB-clock guards remain in force.

The existing slice-one receipt loader is unchanged. Expected
CatalogReceiptUnavailable is narrowly converted to a fixed ValueError at the new
owner boundary so current dispatch and historical callers retain their controlled
failure mapping. Unexpected database/callback failures are not caught there.

## Qualification Method And Scope

The new fixture uses actual owner discovery, saved-input HTTP, reporting/selected
MockHTTP acquisition and owned media upload. It then invokes the genuine standalone
V6 reader/composer and explicitly stores a version/dependency graph for retained
port qualification. This is not service/save/API-generation qualification and does
not qualify a five-second final-save interval. No V5 document is retagged.

Evidence is local at `/workspace/inlet-evidence/20261011/owner-review-retained/`.

- `sqlite01`: overlapping positive smoke, passed one case. Do not add it to distinct
  coverage totals.
- `both02`: five passed, one fixture failure, 100.970 seconds. Four nonempty/empty
  current/history positives passed across SQLite/PostgreSQL, and the SQLite
  missing-link failure boundary passed. The opaque-negative fixture attempted an
  UPDATE of immutable receipt metadata; the existing trigger correctly refused it.
  Replaced only this test fault with the previously used detached-loaded-row scalar
  fault; no trigger or production integrity guard was weakened.
- Initial Ruff preparation reported import/line formatting, corrected before tests.
- `mypy03`: six errors caused by misplaced test-only type-ignore comments after
  formatting. Replaced them with explicit Any casts for the intentional no-SQL
  sentinel. Production typing had passed the source preflight.
- `remaining03`: all 21 passed, zero skips/errors/failures, 286.627 seconds. Selection
  excluded the five already-passed database nodes and included the corrected opaque
  case, other unrun cases, and two direct public-wrapper regressions. Across the
  runs there are **26 distinct passed nodes**: 24 SQLite/PostgreSQL retained-port
  cases and two pure wrapper cases. The smoke overlaps; the failed opaque attempt
  is not counted as another success.
- Two SQLAlchemy cleanup warnings were retained when tests deliberately replaced
  the Connection transaction; neither is a production-path warning.
- Final whole Ruff passed; configured no-path mypy passed all 1470 source files;
  `git diff --check` passed. No further pytest was run.

The bounded cases cover empty/nonempty intents, complete witness/dependency sets,
missing/extra dependencies, unchanged V5 public refusals, original link and opaque
commitment integrity, current media/reporting/session changes with independent
history, Session/Connection replacement, late owner-link removal, final expiry,
and unexpected delegate error propagation. Read access includes viewer membership
and canceled entitlement. Broader actual service generation/history/export/UI
qualification belongs to the following integration package. No claim is made that
this component suite covers every future integration behavior.

`manifest.json` in the evidence directory records exact source/test hashes, complete
log/XML hashes, base commit and node reconciliation. The commit itself is recorded
in a separate local `frozen-head.txt` after commit to avoid a self-referential hash.

## Review Repairs

Source review identified and repaired the typed receipt-error mapping, public V5
creative dependency refusal, and malformed public V5 currentness error normalization.
New direct no-SQL regression covers the latter; actual missing-link current/recheck/
history tests cover the receipt mapping. Legacy validators and original receipt
storage were not broadened.
