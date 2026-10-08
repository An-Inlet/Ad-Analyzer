# Plan-Bound Sales Progress UI — 2026-10-08

Branch: `codex/inlet-planning-progress-ui`, based on frozen interface `133993d`.

Implemented a display-only `plan-progress.mjs` renderer and an explicit **Read Sales Progress** control in the existing planning page. The renderer binds the response to the displayed immutable document, version, digest and complete confirmed goal, independently of editable input revisions. It keeps the two backend goal-digest domains distinct. Available amounts use only the server-computed canonical signed decimal string and BigInt, including values beyond JavaScript's safe integer range. The original target, closed-day prefix, coverage extent, source watermark and as-of time remain visible. Missing/changed-goal results never invent zero or substitute a new goal.

The controller uses the existing no-store, original-cookie, epoch and trailing-session checks. It captures the displayed document before IO and checks that the exact document, plan, workspace, version and digest remain displayed immediately before rendering. Clearing a document, navigation, session invalidation or errors also clears sales. Historical/expired documents can request this independent observation without altering plan eligibility or manual history.

Validation at this checkpoint:

- `pytest -q tests/test_planning_progress_view.py`: 1 actual Chromium DOM test passed. Covers exact unsafe positive and negative amounts, zero, sub-unit negative values, malformed/noncanonical/beyond-int64 strings, safe-number disagreement, foreign scope/version/digest/goal, authority contradictions, changed-goal unavailable, matched unavailable/not-started, literal text and clear-on-rejection. Pure renderer performs no IO.
- `ruff check .`: passed.
- Repository CI command `mypy`: passed, 1086 source files. Earlier `mypy app` also passed (613 files); exploratory `mypy .` failed duplicate module discovery for the existing restore script, so the configured CI invocation was used.
- JavaScript syntax checks for renderer/controller and `git diff --check`: passed.

This checkpoint does **not** qualify the actual progress API or authenticated controller/browser journey. Backend implementation is a separate lane. After reviewed integration, exercise actual generated-plan sales reads, a real Shopify ledger correction followed by an explicit reread, immutable artifact/manual-history separation, historical/changed-goal responses, and original-session/late-response rejection. No schema, backend, provider, or advertising execution code changed. No live requests, deployment or Full run.

## Independent Review Repairs

The initial renderer incorrectly limited a summed sales total to a single signed-bigint row. Removed that restriction. The display accepts up to 512 canonical magnitude digits: this exceeds even the theoretical number of distinct 64-character Unicode `CommerceEntry.entry_key` values for one store multiplied by the signed-bigint row magnitude (less than 424 digits). This is a rendering resource bound, not a spending or per-row financial rule. Tests preserve exact positive and negative totals beyond 2^63 and a 512-digit total; the nested numeric JSON field can overflow to Infinity and is never used to reconstruct digits. Safe integer discrepancies, NaN and fractional nested values still fail.

Matched responses now require the exact saved definition metadata for every sales status; all-null metadata is rejected even for unavailable/not-started sales. An unavailable outer binding continues to require `sales=null` and preserves the original goal.

Repair verification: focused actual Chromium DOM test passed; Ruff, configured mypy (1086 files), renderer syntax and diff checks passed. Authenticated controller/browser qualification still awaits reviewed backend integration.

## Integrated Authenticated Browser Qualification

Fast-forwarded the isolated UI branch to reviewed combined root `38ed75d` (backend `70c0ede`, UI `07fe34b`). Follow-on source change only humanizes the finite validated status/reason/coverage labels; no backend or authorization change.

Actual Chromium over local HTTPS now exercises the real customer routes and SQL service on SQLite and PostgreSQL, with the existing synthetic identity and native MockHTTP fixture. The browser creates a draft (no progress control), generates the plan (no automatic progress request), explicitly reads observed -USD 10, records a separate unverified customer application report, creates a second plan version, selects historical version 1, and reads corrected -USD 20 after an actual owned `CommerceSyncService` reimport. The fixture-only correction endpoint uses real import code with a synthetic measurement reader; it does not stub the progress API. A second fixture endpoint performs a real goal revision for the unavailable-binding case.

Assertions cover original goal/version/digest, exact exported immutable document equality, current export-wrapper freshness reflecting history, no-store GET, no automatic reads, preserved manual-report provenance, two saved versions/one customer event/zero execution attempts, clearing on version navigation, and an actual same-owner login replacing the cookie while a real progress response is held. The old callback is discarded and both document/progress clear. An explicit session refresh permits a new read, a changed goal shows no replacement amount, and logout clears the display.

Final command:

`AD_ANALYZER_TEST_POSTGRES_URL=<local disposable test database> AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true pytest -q tests/test_planning_documents_browser.py -k progress tests/test_planning_progress_view.py --junitxml=/tmp/inlet-progress-ui-final.xml`

Result: **3 passed, 0 skipped, 12.546s** (two actual HTTPS database journeys plus the renderer DOM test). Retained JUnit: `/workspace/inlet-evidence/20261008/planning-progress-ui/final.xml`. Whole Ruff and configured mypy passed (1090 files); controller/renderer/driver syntax and diff checks passed.

Qualification notes: initial browser pass used an incorrect export URL; review corrected it to require a successful real export. The next two cases failed an overstrong whole-export equality assertion because `PlanReadResult` intentionally includes current freshness/input-head metadata. The final test compares exact immutable document and digest while separately checking the changed historical freshness label. These were fixture corrections, not production defects. Provider IO remains simulated; no live qualification or Full run. Later closed-day expansion remains covered by the separately reviewed backend package, not this browser journey.
