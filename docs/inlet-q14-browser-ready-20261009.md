# Q14 Browser Acceptance — Checkpoint And Qualification

Base `a84183d` (approved interface on `3b39199`); branch `codex/inlet-q14-browser-acceptance`, worktree `/workspace/inlet-q14-browser-acceptance`.

Initial checkpoint `5753778` was prepared with browser/database qualification explicitly queued. The record below preserves that checkpoint; the subsequent authorized terminal result is recorded in the final section. Root required waiting for the original frozen aggregate to finish or explicit go-ahead. No aggregate source/database, production code, provider scope, clock, TTL, policy or API contract changed.

- `tests/planning_target_inventory_fixture.py`: runtime-closed Google/Meta/TikTok platform and ordered original→absent→replacement states. Wraps existing MockHTTP responses, preserving actual collector/catalog/receipt paths. No arbitrary fixture payload or authority mutation.
- `tests/javascript/planning_target_disappearance_browser.mjs`: actual portal controls create/save original allocation, observe fresh disappearance, reject unconfirmed removal, cancel and generate exact original as-of V1, explicitly reread/select same-name native-ID9 replacement, generate V2, and check original history/artifact. Exact owned account, native ID, canonical and selection keys are used. It does not claim original receipt is revoked by a new empty catalog.
- Existing HTTPS harness adds three provider journeys and only two fixed POST fixture phase controls. Generation native-call counts are captured around the unchanged actual route dispatch; final assertions require two input receipt links, not two total catalog receipts. Original API disappearance test is untouched.
- Six small no-DB tests check unsupported platforms, skipped/replayed/reset/unknown phases. They qualify only the private state machine, not browser behavior.

## Checks Actually Run

```
/workspace/inlet-venv/bin/pytest -q tests/test_planning_target_inventory_fixture.py \
  --junitxml=/workspace/inlet-evidence/20261009/q14-browser/helper-final.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
node --check tests/javascript/planning_target_disappearance_browser.mjs
git diff --check
```

Raw logs under `/workspace/inlet-evidence/20261009/q14-browser/`. Initial mypy identified stale literal narrowing across mutating fixture methods in a test assertion; an explicit string comparison prevents incorrect static narrowing without changing phase semantics. Original error log retained as `mypy.log`. Final results recorded at freeze; no browser pass is inferred from syntax/static checks.

## Recorded Qualification Command — Initially Queued

Executed only after root reported the original aggregate terminal and authorized this bounded command. Approved isolated schema environment:

```
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true \
/workspace/inlet-venv/bin/pytest -q tests/test_planning_documents_browser.py \
  -k 'target_disappearance or targets' \
  --basetemp=/workspace/inlet-evidence/20261009/q14-browser/browser-artifacts \
  --junitxml=/workspace/inlet-evidence/20261009/q14-browser/browser.xml
```

Expected selection: six new disappearance/replacement cases and six existing target-picker compatibility cases across three providers and both databases. This is not an aggregate rerun. Keep all real expiry/failure outcomes; no hidden clock freeze, TTL increase or retry. Driver result artifacts retain sanitized selectors, native IDs, original/replacement receipt expiries, V1/V2 digests and generation native-call checkpoints.

Unknown-parent topology, simultaneous duplicate-name behavior and unsupported manual verification remain separate Q14 gaps. No Full Q14, comprehensive quality, live-provider or deployment qualification is claimed.

Freeze checks: **6 helper tests passed, 0 skipped, 0.207 seconds**; whole Ruff, bare mypy1,125, Node syntax and diffcheck passed. Browser qualification remains queued.


## Authorized Terminal Browser Result

Root reported original aggregate terminal and authorized the exact queued command. Tested code head remained clean `5753778`; no source edits, retries, TTL/clock/timeout relaxations or broader suite runs were needed.

**12 passed, 0 skipped, 104.561 seconds**: six new disappearance/replacement cases plus six existing target-picker compatibility cases, Google/Meta/TikTok on SQLite/PostgreSQL. This is one bounded invocation, not a Full run or a claim about the failed frozen aggregate. Raw terminal `browser.log`, JUnit `browser.xml`, and sanitized `browser-result-index.json` are retained in `/workspace/inlet-evidence/20261009/q14-browser/`; the index points to all six new per-case browser artifacts.

Actual browser observations establish:

- Fresh empty inventory shows honest coverage, clears target controls and cannot silently save removal without replacement confirmation. Cancelling the draft preserves the original saved selector.
- Original unexpired as-of receipts still generate exact V1 after a fresh empty observation, without native rereads. This is not proof that the original target still exists.
- Same-name native-ID9 replacement has different canonical/selection keys, visible native identity and no prefilled old allocation. Unconfirmed save sends no mutation; explicit selection/confirmation creates revision/version2.
- V1 document and artifact digest remain exact; V2 retains the exact new owned selector/native ID. History/artifact assertions use read-only API calls within the browser, not an export-button interaction claim.
- Each graph contains one plan, two inputs, two versions, two **input receipt links**, zero events and zero execution attempts. Three catalogs were observed; total catalog receipt count is not conflated with input links.
- Server checkpoints independently show no native calls during either generation: Google18→18 and27→27; Meta/TikTok10→10 and15→15 on both databases.

Whole Ruff, bare mypy1,125, Node syntax and diffcheck passed at the tested head (`ruff-browser-head.log`, `mypy-browser-head.log`, `node-browser-head.log`). This successor changes only this evidence ledger. Existing non-dated setup/real receipt expiry, 55-second per-case harness limit and all production guards remained unchanged.

Q14 remains partial: unknown-parent topology, simultaneous duplicate-name saved-target behavior and unsupported manual verification are not covered by this package. No live provider or production readiness claim follows.
