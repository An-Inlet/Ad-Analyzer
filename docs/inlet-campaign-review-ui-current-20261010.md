# Current Campaign Review UI Regression Closure — 2026-10-10

Implements reviewed484e6c4 contract on isolated baseeb8afe0, with approved exact
Google-null source metadata correction. No production files changed. Unlike the
social retained-shell package, current campaign-review HTML/modules/API remain the
actual working offline-plan UI. Full original JavaScript is unchanged.

## Construction And Current Scope

New closed SourceLifetime profile campaign_review_ui invokes one literal driver at
PIN2155ff3. The original25-statement setup prefix through three-account policy edit/
approve/commit is AST-identical; proof saved in `source-prefix-ast.json`. Original
Google, Meta101 and TikTok202 remain ordered in one approved legacy policy, caps
100/80/50 and original period/audit/source metadata intact. Google account timezone
is genuinely null; Meta/TikTok UTC, policy UTC. No inferred metadata or row rewrites.

Driver stops before media/drafts. Actual CURRENT services upload original PNG/create
original Google+Meta drafts. Full current browser then uploads real encoded MP4,
creates all three provider drafts, decodes image/video, tests private media denial
and blob revocation, offline approval, XSS-safe edit, concurrent revision/stale
approval and actual owner→viewer denial. Original Python final revision assertions
remain unchanged. Real auth stays on its real clock/ordinary TTL; existing local
campaign API JourneyClock is preserved. No fake provider posts/capability exceptions.

Parent/child check exact owned SQLite file or loopback disposable PG schema, empty
all-table graph before source, strict bounded scalar output/current owned bindings.
Complete original graph/physical schema retained. Expected graph changes are only
current5drafts/7revisions/2media, original Google1 offline approval, real1session/
1token receipt, exact customer membership role→viewer. Original user/email/source/
legacy policy/audits and all financial state stay exact. No new execution authority.

Expected policy/account/window snapshot is copied before browser requests; expected
bodies use only fixed driver values and exact validated media IDs/bytes. Every current
artifact is independently reconstructed from those expected typed inputs/current
immutable source and compared with canonical digest/row fields. Actual media bytes
are read back, not merely hashes accepted. Whole baseline is independently copied
from the parent snapshot; copied baseline/source/auth/extra rows/foreign scope/hash/
approval/role and repeat-login adversarial cases fail. Browser file and current
HTML/components hash equality retained in `unchanged-current-source.json`.

The literal driver constructs no HTTP adapter; provider_posts0 is source-established,
not a measured remote counter. Actual current browser requests are localhost only.
Legacy approved source is compatibility provenance, not current spending permission.

## Evidence And Qualification

Durable evidence root:
`/workspace/inlet-evidence/20261010/campaign-review-ui2/`.

- `gate.log/xml`: 1setup error8.475s, before current setup/browser. New validator
  incorrectly assumed original Google timezone UTC. Actual source rows showed
  GoogleNone/MetaUTC/TikTokUTC. `failed-gate-artifacts/` preserves source database,
  IDs/logs and original failure; corrected only expected invariant after review.
- `corrected-gate.log/xml`: SQLite1 passed10.736s. `corrected-gate-proof/` retains
  IDs/SourceLifetime/producer/browser proof. No original failed run credited.
- `qualified.log/xml`: original current browser2 plus unchanged shell/assets1 passed;
  precise terminal timing below. Subsequent independent baseline-copy tightening
  intentionally requalifies affected browser2 in final compatibility run.

No source reset, DB reset, live verification, Full/aggregate or historical batch run.
Only two original failed identities are candidate recovery; shell and compatibility
are overlapping supporting checks, never additional original-failure credit.

## Exact Commands

From `/workspace/inlet-reported-preview-consumers`, pytest executable
`/workspace/inlet-venv/bin/pytest`, with
`AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci`
and `AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true` (owned schemas only):

```text
-q tests/test_campaign_review_ui.py::test_review_browser_real_api[sqlite]
 --basetemp=/tmp/inlet-campaign-ui2-gate-20261010 --junitxml=<evidence>/gate.xml

-q tests/test_campaign_review_ui.py::test_review_browser_real_api[sqlite]
 --basetemp=/tmp/inlet-campaign-ui2-corrected-gate-20261010
 --junitxml=<evidence>/corrected-gate.xml

-q tests/test_campaign_review_ui.py
 --basetemp=/tmp/inlet-campaign-ui2-qualified-20261010
 --junitxml=<evidence>/qualified.xml

-q tests/test_campaign_review_ui.py::test_review_browser_real_api
 tests/test_campaign_review.py::test_exact_review_edit_and_stale_approval
 tests/test_campaign_review.py::test_review_binding_rechecks
 tests/test_planning_customer_boundary.py
 --basetemp=/tmp/inlet-campaign-ui2-compat-20261010
 --junitxml=<evidence>/compat.xml
```

All logs match XML prefix, outside/tmp from start. Unique supporting source IDs/logs/
results copied durably before checkpoint. Earlier restart wiped unrelated previous
/tmp contents; nothing here implies those files were retained.

## Final Results And Review Follow-Up

- Precursor module3 passed26.202s (`qualified.log/xml`).
- Final affected browser2 plus current exact-review2/current binding10/default
  boundary8: **22 passed121.469s**, no skips/errors (`compat.log/xml`). This run
  includes independent parent/evidence baseline-copy identity and tamper negative.
- Review tightened the new IDs reader to `lstat`, explicit non-symlink/regular-file
  check and8192-byte bound BEFORE read/parse, preserving strict exact scalar schema.
  Focused new `tests/test_campaign_review_ui_source_guards.py`: **8 passed2.018s**,
  regular-file positive and symlink/directory/missing/oversize/list/bool/extra-field
  negatives. Synthetic scalar values test parsing only, never source authority.
  Command: `pytest -q tests/test_campaign_review_ui_source_guards.py
  --basetemp=/tmp/inlet-campaign-ui2-guards-20261010 --junitxml=<evidence>/guards.xml`.
  Final parser also reread both actual SQLite/PG browser source IDs successfully;
  exact file paths/hashes saved in `final-read-ids-actual-artifacts.json`. No redundant
  browser rerun after this file-only guard change, per independent review instruction.
- Whole `/workspace/inlet-venv/bin/ruff check .` passes (`ruff-final.log`).
  `MYPY_CACHE_DIR=/tmp/inlet-campaign-ui-mypy /workspace/inlet-venv/bin/mypy` passes
  **1245source files**, bare invocation (`mypy-final.log`). Node syntax check of full
  unchanged driver and `git diff --check` pass after last code change.

`qualified-proof/` and `compat-proof/` retain structured browser pass results, actual
source IDs, bounded producer logs and SourceLifetime manifests. Final artifact SHA256
index is `final-artifact-manifest.json`. Failed initial SQLite source database remains
in `failed-gate-artifacts/`; no logs or source evidence were deleted/replaced.

Current source is ready for final independent review. No tests active at freeze.
No claims beyond current offline review and explicitly described legacy provenance.
