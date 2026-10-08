# Owned V3 Window Collection And Final Recheck

Branch `codex/inlet-window-adapter`, worktree `/workspace/inlet-window-adapter`,
base `4fc2b94`. Implements bounded package B in
[the runtime freeze](design/planning-window-runtime-packages-v1.md).
Only new `window_adapter.py`, `window_local.py`, focused tests and this ledger.
No old adapter/composer/ports/service/repository/routes/defaults or migrations changed.

## Behavior

`OwnedWindowEvidenceReader` accepts explicitly injected canonical v3 tickets/policy.
It refreshes identity before SQL contexts, verifies exact original actor/session,
goal and source fences, captures complete reporting pins including absence, and
collects actual native catalogs or reuses the exact saved receipt. No old full
adapter is called and no fake legacy bundle is constructed. Existing narrow native,
receipt and Shopify readers are used directly. The old fixture policy `1` stays
unchanged; new tests construct canonical v3 tickets at the explicit seam.

Every catalog campaign receives a success or known gap for every primary/comparison
window. An owned context shares presence parsing across its account slots and closes
before further reads or persistence. Original reports/headers remain intact;
requested projection references have distinct normalized window keys. Selected
presence, missing cells and missing calendar days remain separate from zero.
Google/TikTok without selected presence retain catalogs with explicit per-window
gaps. Empty collected scope is not global provider absence. Combined slot/byte
bounds refuse rather than truncate; expiry derives only from actual native catalogs.

Native authorization/provider/metadata failures propagate; no broad catch converts
them to catalog gaps. The existing known >366-day diagnostic constraint is handled
as an explicit collection limitation; if all catalogs are unavailable, collection
aborts before inventing a deadline. This package adds no provider-failure receipt or
claim that a DB-only recheck proves current provider availability. Trusted transient
bundle provenance belongs to the current operation, as specified in the freeze.

`recheck_window_sources` requires a current DB-only authorization callback and live
clock callable. It reconstructs every successful projection and known reader gap
with fresh owned contexts and full source pins, verifies saved catalogs/receipts,
reconstructs actual goal progress, and checks current source/privacy/session/paid-work
and expiry after waits. Commerce equality excludes only the newly sampled `as_of`;
all semantic source, goal, coverage, amount, reason and watermark fields must match.
Fresh `as_of` cannot precede the observed value. Window matching uses the frozen
UTC-instant helper, not Python's same-zone fold equality. Context listeners close
before caller writes. Existing caller CAS and final persistence guards remain
necessary; arbitrary constructed DTOs are not an ownership attestation.

## Actual Qualification And Limits

The new tests use owned SQL sources, actual native MockHTTP collectors, real receipts,
real reporting readers, and actual Shopify/goal reads. Most positive/zero/missing
cases use the existing valid installed SQL sidecar fixture and do not claim a raw
provider import. A separate case runs the actual Meta 0090 rolling producer over
56 closed days using MockHTTP, then invokes this adapter and final rechecker for
seven-day primary and preceding seven-day comparison windows. Counts are distinct
(10 versus 3), original total remains 13, original header retains all 56 days, and
both requested references survive. A legacy metric correction outside both slices
invalidates the original whole manifest and prevents final acceptance.

Other coverage: all three platforms' genuine missing sidecars; primary success with
out-of-range comparison; explicit empty native scope versus absent current report;
absence becoming available; mapping/generation/privacy/session/sidecar/commerce
changes; native HTTP denial abort; no all-unavailable invented TTL; real saved
receipt reuse without native rereads and its original expiry; identity IO outside
SQL; clock expiry injected only after final commerce reconstruction; caller rollback;
actual ownership denial and original-session mismatch. Goal unconfirmation and owner
membership suspension are separately qualified below. The actual HTTP create/receipt
routes establish inputs for receipt reuse; generation itself is an explicit adapter
call, **not** newly activated customer API generation.

Raw artifacts: `/workspace/inlet-evidence/20261008/owned-window-adapter/`.

- Initial adapter cohort: **32 passed, 76.37 seconds** (`initial.log`).
- Added import/empty/receipt cohort initially: **4 passed, 1 failed**, because a test
  ticket's prepared_at preceded the newly saved input. Fixed only the fixture's
  actual preparation time; original guard unchanged (`additions.log/xml`).
- Receipt repair: **2 passed, 36 deselected, 6.90 seconds** (`receipt-repair.log`).
- First complete module: **40 passed, 73.27 seconds** (`final.log/xml`).
- After aligning final matching to exact UTC instants, rerun: **40 passed, 0 skipped,
  90.17 seconds** (`qualified.log/xml`). These overlapping cohorts are not summed.
- Actual goal unconfirmation/owner suspension: **4 passed, 40 deselected,
  12.74 seconds** (`authority.log/xml`), both databases.

Whole Ruff and bare mypy (1,100 source files) pass. Initial static runs identified
one tuple annotation and formatting issues, corrected before final qualification;
no static failure is represented as a pass. Diff whitespace check passes.
Commands use the approved disposable PostgreSQL URL/flag and isolated fixture schemas:

```text
pytest -o addopts='' -q tests/test_owned_window_adapter.py --junitxml=.../qualified.xml
pytest -o addopts='' -q tests/test_owned_window_adapter.py -k 'changed_source and (goal or owner)' --junitxml=.../authority.xml
ruff check .
mypy
git diff --check
```

## Remaining Gates

Independent review and integration are pending. The new v3 composer is a separate
lane. This package does not wire service/repository dispatch, alter current v2
activation, or implement comparison UI/public schema. Actual import-to-customer-API
v3 generation/current/history/export, representative large multi-platform plans,
and affected dispatch/archive regressions remain later acceptance gates. It does
not close frozen expert quality cases or claim live/purchasable readiness. No live
provider calls, advertising writes, Full aggregate, remote CI, deployment, or merge
into main occurred.
