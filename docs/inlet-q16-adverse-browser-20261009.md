# Q16 Session Replacement And Goal Revision Browser Acceptance

Isolated branch `codex/inlet-q16-adverse-browser`, base `4982685`.
Root froze the private twelve-case interface before implementation. Only the
explicit dated browser test/driver and this ledger change. Shared fixture,
production code, clocks, validators, TTLs, advertising guards, W1 source/database
and live provider access remain unchanged.

## Added Cases

The original eight browser cases remain. Two October-only branches run on both
SQLite and PostgreSQL, adding four cases:

- **Same-owner replacement during held progress.** Actual October UI decision
  and unverified report precede the November initial zero read. Another actual
  computed progress response is held. A fresh real login replaces the session
  at the *same* November timestamp, not a later day. The public browser checks
  same user, equal expiry and changed CSRF continuity cookie. The private
  harness reads the actual presented session row before login and proves its
  subsequent `revoked_at` equals issuance time and is strictly before expiry.
  No session identifier, digest or authority object is exposed to the driver.
  Explicit refresh/reopening restores the original accessible plan and genuine
  history. After consuming the held response's real cloned body and allowing
  the controller's continuation to run, stale progress remains absent. The
  original Response, status and bytes are preserved. This tests client-side
  stale callback rejection, not withdrawal of bytes already computed.
- **Confirmed current goal revision.** After actual October UI records, the
  browser uses real customer HTTP GET/PUT/preview/confirm with its normal CSRF
  token to revise the current target from $12,000 to $13,000. Only after that
  does the legitimate initial November import/session stage run. An explicit
  UI progress read shows Goal Changed and no replacement sales amount. The
  original V1, document digest, saved $12,000 goal and exact event payloads are
  unchanged. The confirmed-goal API operations are HTTP acceptance, not a claim
  of using a goal-editing UI.

All actual progress reads snapshot retained database counts immediately before
and after the production handler, so expected prior goal revision rows are not
misclassified as read writes. Native request count remains fixed after initial
plan generation. The goal-change response must have `sales=null`; neither it
nor session replacement grants execution authority.

Existing erasure branches now explicitly require 404 from the old `/events`
and `/versions` collection URLs as well as plan/version1/progress/export.
The natural report timestamp wait now uses strict `floor(generated minute)+1`,
preventing JavaScript's submillisecond timestamp truncation from rounding an
application time before actual generation. It remains at most 60 seconds;
production freshness checks and the existing 150-second test harness bound stay
unchanged.

## Retained Evidence And Scope

Evidence root: `/workspace/inlet-evidence/20261009/q16-adverse-browser/`.
Per-case artifacts retain the original generated document, scalar fixture IDs,
actual customer event payloads, browser results and real progress responses.
Replacement cases additionally retain only the nonsecret revocation/expiry
integer timestamps in `session-rotation.json`. The synthetic generated artifact
is unscored and not expert approved. This package does not qualify comprehensive
Q16 recommendation quality, causal effects, image understanding, production
integration or live delivery.

## Initial Observation And Clock Boundary

Initial new-case invocation (`first.log/xml`): one passed, one failed in
107.153 seconds. Actual SQLite session replacement passed. The changed-goal
case correctly returned HTTP200 with `binding_reason=goal_changed`, `sales=null`
and the original goal when the driver incorrectly expected a pre-login401.
The dated progress clock does not advance real authentication time: this
unavailable projection returns before the matched goal-sales reader, while its
planning authentication remains checked against actual October time. The
previous October session was therefore still time-valid for that projection.

The final new goal-change branch issues its fresh ordinary November session
without making that invalid expiry assertion. Original eight matched-path
assertions remain; their 401 observations are from the dated sales path and must
not be generalized as proof that the real global auth clock advanced. The new
same-owner replacement proof is independent and uses the actual old session's
revocation while strictly unexpired. No production behavior was changed in
response to this fixture expectation failure.

## Commands

With the existing disposable, nonaggregate PostgreSQL test configuration:

```sh
/workspace/inlet-venv/bin/pytest -q tests/q16_browser_acceptance.py \
  --basetemp=/workspace/inlet-evidence/20261009/q16-adverse-browser/final-artifacts \
  --junitxml=/workspace/inlet-evidence/20261009/q16-adverse-browser/final.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
node --check tests/javascript/q16_browser.mjs
git diff --check
```

The earlier new-case invocation selected only `session_replacement or
goal_changed` with `-x` and retained separate `first-artifacts` and `first.xml`.
It is not added to the final cohort total. Ruff initially corrected one import
ordering issue; whole Ruff and bare mypy1123 then passed, as did Node syntax and
diff checks. No broad/full aggregate was run or restarted.

Final qualification: **12 passed, 0 skipped, 445.486 seconds** in
`final.log/xml`. This single count includes the original eight plus four new
adverse cases on both databases. Final source passed whole Ruff, bare mypy1123,
Node syntax and diff checks. After terminal, only the previous-day assertion's
failure-message text was clarified to “matched dated sales path rejects
previous-day session”; no condition or behavior changed. Node syntax and diff
checks passed again after that prose-only edit; the behavioral cohort was not
repeated. No advertising attempt or new product capability was introduced.
