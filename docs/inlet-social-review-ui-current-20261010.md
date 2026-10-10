# Social Review Browser Regression Closure — 2026-10-10

Package implements reviewed1a0ece4/e4166a8 fixture contracts and the approved narrow
ORM timestamp correction. No production changes. The four original identities now
exercise an explicitly retained HTML shell with CURRENT component modules, full
unchanged JavaScript driver and actual CURRENT review APIs. They do not claim that
those action controls are present on the current customer page. Two supplemental
cases exercise the actual current `/app/social-configuration` History route.

## Source And Invariants

- Exact hashed3032-byte HTML from PIN2155ff3, literal selected path; only fixture-start
  serves it. No historical JavaScript or runtime fallback. Current component is
  byte-identical to PIN; driver file unchanged, only served actor literal substituted.
- New closed ui consumer retains whole original graph/physical schema. Precomputed
  current review/digest, actual encoded owned TikTok media, ordinary actual sameactor
  login/logout and exact cookies/token receipt digests. Only one review/confirmation;
  no provider writes or new financial effect rows. Existing producer/config/API
  consumer behavior/defaults unchanged.
- Original workspace XSS-name test retained. One actual ORM updated_at within real
  commit bounds is bound once with the exact name; original baseline and all other
  rows remain exact. Later auth/final graph comparisons reuse this fixed row.
- Current History cases invoke actual ASGI router and verify exact current HTML
  before substituting only the test driver script. Full unchanged history driver
  proves read-only controls, scoped API, changed-session clearing, foreign denial,
  zero execution runs/attempts and no advertising writes.
- Adversarial copies reject original-auth mutation, unbound evidence, extra sessions/
  reviews/approvals, wrong actor/CSRF/workspace fields, timestamp bounds and repeated
  name binding. No global capability override or table exemptions.

## Failure Evidence Retained

Evidence root: `/workspace/inlet-evidence/20261010/social-review-ui4/`.
Unique basetemps are `/tmp/inlet-social-ui4-*-20261010`; failed complete artifacts
were copied durably before checkpoint. The earlier restart wiped prior /tmp data;
this package does not claim those old temporary files survived.

- `gate.log/xml`: two60s timeouts plus two strict teardown errors,144.347s. Current
  static file was History, old script replacement no-op, so neither driver started.
  Zero login/review rows. `failed-gate-artifacts/`, source snapshot/diff/manifest retained.
- `shell-gate.log/xml`: two login-result failures plus two teardown errors,21.148s.
  Actual login rows were committed; recorder rejected incomplete expected workspace
  delta. This is not evidence of product authentication denial.
- `login-diagnostic.log/xml`: one failure plus one teardown error,13.304s. Sanitized
  traceback identifies recorder full-graph equality. Actual failed SQLite workspace
  created_at18:49:56.885330 / updated_at18:49:59.025672 matches automatic ORM update.
  `failed-shell-gate-artifacts/` and `failed-login-diagnostic-artifacts/` preserve DB,
  source IDs/logs, browser results and profiles. No cookie values logged by recorder.
- `corrected-gate.log/xml`: two SQLite cases passed21.640s. Supporting source IDs,
  native-zero proof and browser results copied to `corrected-gate-proof/`.

Earlier failed runs are not counted as passes. Gates and compatibility overlap, not additive coverage.

## Exact Qualification Commands

All pytest commands ran from `/workspace/inlet-reported-preview-consumers` with
`AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci`
and `AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true`. PG uses independently owned schemas;
no shared database reset. Executable `/workspace/inlet-venv/bin/pytest`.

```text
-q tests/test_customer_social_review_ui.py -k sqlite
  --basetemp=/tmp/inlet-social-ui4-corrected-gate-20261010
  --junitxml=<evidence>/corrected-gate.xml

-q tests/test_customer_social_review_ui.py
  tests/test_current_advertising_history_browser.py::test_current_history_pages_preserve_scope_and_have_no_action_controls[sqlite-social-configuration]
  tests/test_current_advertising_history_browser.py::test_current_history_pages_preserve_scope_and_have_no_action_controls[postgres-social-configuration]
  --basetemp=/tmp/inlet-social-ui4-qualified-20261010
  --junitxml=<evidence>/qualified.xml

-q tests/test_customer_social_review_api.py
  tests/test_social_configuration_review.py::test_exact_configuration_confirmation
  tests/test_planning_customer_boundary.py
  --basetemp=/tmp/inlet-social-ui4-compat-20261010
  --junitxml=<evidence>/compat.xml
```

`<evidence>` is the durable root above. Logs use the same prefix. Earlier first gate
and shell gate used the first command with basetemps `inlet-social-ui4-gate-20261010`
and `inlet-social-ui4-shell-gate-20261010`; diagnostic selected only
`test_social_review_real_browser[sqlite-meta_ads]`, basetemp
`/tmp/inlet-social-ui4-login-diagnostic-20261010`.

Final browser cohort: **6 passed,52.880s**, no skips/errors. Four original identities
are retained-component regression recovery; two actual current History route cases
are supplemental. `qualified-proof/` and its SHA256 manifest retain source IDs,
SourceLifetime/producer logs and full browser result/status records.

Static commands: `/workspace/inlet-venv/bin/ruff check .`;
`MYPY_CACHE_DIR=/tmp/inlet-social-ui4-mypy /workspace/inlet-venv/bin/mypy`;
`node --check tests/javascript/social_configuration_browser.mjs`;
`node --check tests/javascript/current_advertising_history_browser.mjs`;
`git diff --check`. Whole Ruff/bare mypy1237/Node/diff pass on final code.
No Full/aggregate, hosted verification, provider writes or current-page action claim.


Compatibility: **16 passed,97.307s**, no skips/errors (`compat.log/xml`): API4,
configuration positives4, unchanged default planning boundaries8. Source IDs/producer
proof retained in `compat-proof/`. These overlap prior qualified packages and add no
new original-failure identities.

Review caught that the first new History instrumentation returned a fresh Response,
dropping current security/cache headers. Corrected to send the actual response-start
with identical status/all ordered headers, changing only Content-Length, and the
instrumented body. Explicit nonlength-header equality check added. No product change.
Affected-only final command uses `tests/test_current_advertising_history_browser.py
-k social-configuration`, basetemp `/tmp/inlet-social-ui4-headers-20261010`,
`headers.log/xml`: **2 passed,5.177s**, no skips/errors. Precursor six-case
result remains separately recorded; only these two cases needed repeating. Whole
Ruff/bare mypy1237/Node/diff rerun after this last code change and pass.

Frozen source has no running tests and no known blocker. Independent final review is
pending. Coverage scope remains original retained-component4 plus supplemental
current History2; no claim of live/native customer behavior or action-page availability.
