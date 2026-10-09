# Dated Q16 Browser Acceptance — 9 October 2026

Branch `codex/inlet-q16-browser`, based on reviewed fixture `c597300`.
This is partial Q16 acceptance, not a full quality or expert-review pass.

## Boundary

The explicitly invoked `tests/q16_browser_acceptance.py` is not default-collected.
It uses the unchanged `q16_fixture.py` contract and current production planning
page/controller, FastAPI routes, service, SQL and CommerceSync through local TLS
and real Chromium. Only provider/payment/identity inputs are synthetic. No live
provider access, production changes, advertising writes, global clock patch,
TTL extension, or guard bypass is introduced. Each database fixture owns its
isolated schema; the W1 checkout and aggregate database are untouched.

The private browser driver receives scalar IDs and the actual exported artifact.
Fixture stage requests perform real CommerceSync imports. Actual HTTPS session
issuance narrowly supplies the documented customer-module issuance clock and
coherent synthetic identity claims. Tokens are unique per login. Production
session expiry still rejects the previous day's session with 401. Existing
planning API `utc_now` uses the documented dated read seam; Python's global
clock remains unchanged.

## Verified Current Behavior

Both SQLite and PostgreSQL run these separate branches:

- Progress: the actual existing V1 is displayed; explicit clicks read USD
  0.000000, then 25.000000 after a real imported order, then 20.000000 after
  its real imported refund. New ordinary sessions are issued for later stages.
  America/New_York closed-day coverage crosses the November DST transition:
  initial `[2026-11-01T04:00Z, 2026-11-03T05:00Z)` has two days; later coverage
  ends `2026-11-04T05:00Z` and has three. Artifact document bytes, digest, saved
  $12,000 goal and planning graph remain unchanged. There is no additional
  native advertising read at progress stages.
- Privacy: after initial progress, a second actual computed successful progress
  response is held. Actual workspace privacy erasure and explicit UI refresh
  clear the plan/progress. Releasing those original bytes cannot resurrect the
  DOM because the controller epoch changed. Actual old plan/version/export/
  progress IDs return 404 and the list is empty. This proves client-side late
  response rejection, not server revocation of bytes already computed in flight.

Missing reporting remains visible. Progress makes no manual-application or
attribution claim. Both branches assert zero plan events and zero execution
attempts. No customer decision/manual report is performed in the final tests.
The synthetic image was actually uploaded by the shared fixture, but its use in
this document is only a textual media ID/SHA reference: no image-consumption or
creative quality claim is made.

## Checks And Retained Evidence

Evidence root: `/workspace/inlet-evidence/20261009/q16-browser/`.
Final invocation (using the existing disposable, nonaggregate PostgreSQL fixture
configuration):

```sh
/workspace/inlet-venv/bin/pytest -q tests/q16_browser_acceptance.py \
  --basetemp=/workspace/inlet-evidence/20261009/q16-browser/final-artifacts \
  --junitxml=/workspace/inlet-evidence/20261009/q16-browser/final.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
node --check tests/javascript/q16_browser.mjs
git diff --check
```

Final: **4 passed, 0 skipped, 24.138 seconds** (`final.log`, `final.xml`).
Whole Ruff passed; bare mypy passed all 1122 source files; Node syntax and diff
checks passed. The prior equivalent four-case run also passed in 23.199 seconds
(`third.log/xml`), before adding full original-artifact retention.

Each final case directory beneath `final-artifacts` retains
`original-artifact.json`, `fixture-ids.json`, `browser-result.json`, and
`progress-responses.json`. These are actual synthetic generated artifacts and
actual API response bodies for later human review, **unscored and not expert
approved**. No screenshots were captured. The progress response series includes
actual rejected reads as well as successes. Prior result/progress outputs were
also copied to `third-artifacts` before temporary-directory cleanup.

## Failed Experiments Preserved

- `initial.log/xml`: one SQLite setup failure, 5.637 seconds. The test helper
  retained the old Origin, so the actual API rejected it with 403. Fixed only
  this test's helper-origin binding.
- `second.log/xml`: one SQLite failure, 5.301 seconds. Reusing a synthetic login
  token failed the real one-time session exchange with 401. Fixed by distinct
  login tokens; no production authentication changes.
- `manual.log/xml`: one SQLite failure, 20.721 seconds, from a requested optional
  UI manual-report extension. The November reported-applied date is later than
  the real October clock, and the actual API rejected it with 422. The extension
  was removed, without changing that validator or manufacturing an earlier
  report. This failure is not included in the final four passing cases.
- An intermediate static run on that discarded extension found an optional
  integer addition type error; the final unchanged-count assertion and full
  mypy check pass.

The manual-report chronological gap needs a separately reviewed fixture that
creates/reviews the plan in real October before November progress, rather than
backdating a report or weakening date validation. Full Q16, substantive plan
quality, expert scoring, live deployment and production integrations remain
unqualified by this package.

## Independent Review Repair: Deterministic Late-Response Observation

Review of `08a1664` found that waiting a fixed 200 milliseconds after release did
not prove Chromium had received the held response under load. That earlier
four-case result remains a bounded observation, not the final synchronization
proof. The privacy driver now arms observation of exactly that next progress
fetch, awaits the complete real response body through `Response.clone()`, and
returns the identical original Response to the controller without replacing
bytes, status or headers. After that promise resolves, a following event-loop
task lets the controller's fetch continuation and stale-epoch rejection settle
before checking that the DOM remains empty. The current controller rejects a
stale epoch before parsing its original JSON body; this test does not falsely
claim that controller JSON parsing occurred.

Final repair qualification: **4 passed, 0 skipped, 25.943 seconds** in
`synchronized.log/xml`, with full actual artifacts beneath
`synchronized-artifacts`. Same explicit pytest command as above with those new
artifact paths; whole Ruff, bare mypy (1122 files), Node syntax and diff checks
all passed. No production code, fixture clock, response contents or auth guard
changed. No manual-report extension was added.
