# Social Review UI: Retained Component And Current History Split

Proposal only, superseding the shell assumption in
`social-review-ui-current-fixture-v1.md`. No production restoration or test rerun.

## Observed Failure And Scope

At implementation HEAD15dc7fc the SQLite gate produced two 60-second browser
completion timeouts and two strict source-finalizer errors (144.347s). The harness
loaded `social-configuration.html`, now Advertising History, and replacement of the
old script URL was a no-op. Neither review driver started: no login, token receipt,
review or approval was created. The deliberate workspace-name setup then correctly
failed the unbound graph guard. These are not successful component/API assertions.

Raw log/XML and complete failed temporary artifacts are retained under
`/workspace/inlet-evidence/20261010/social-review-ui4/`; unqualified source copies,
SHA manifest and diff are alongside them. No guard or timeout relaxation is proposed.

Current `/app/social-configuration` intentionally returns `advertising-history.html`
from `app/portal/router.py::customer_social_configuration`. Production must retain
this behavior. Four old identities become explicitly labeled retained-component
coverage, not current customer-page availability or permission to publish ads.

## Closed Retained Shell Interface

Add one test-only immutable HTML fixture extracted from exactly:

- Commit `2155ff3e3ab00cd62057dd86cb49d45359d4f49f`.
- Literal path `app/portal/static/social-configuration.html`.
- Original UTF-8 bytes:3032.
- SHA256 `a2806c2269712abc778295b9cc2c6dbb65cb61f3e270d306542691051799e0de`.

Store as `tests/fixtures/retained-social-configuration.html`; validate its exact hash
before serving. No arbitrary revision/path parameter, historical Python runtime,
old JavaScript extraction or production static override. Serve only the existing
`/__fixture__/start` endpoint. Require exactly one original script URL and replace
it with the existing fixture driver URL. Mark Python test/docstring and ledger as
retained-shell/current-component; preserve original test identities for mapping.

The original script occurrence count is one. Read-only literal DOM-ID checks found
no missing IDs for either the full driver or current component. Current
`app/portal/static/social-configuration.mjs` is byte-identical to PIN (git diff empty),
SHA256 `0b0264c4dc546db62a93d69f685d20d9e6b7c01eedebe2c3793e068b0b102f8d`.
The full driver SHA256 is
`b100dd0ad7a217b7a9ddf3433caf19d3869b6a7c0ea56e065ed520bdcf5e830a`.
These establish source compatibility, not a browser pass. Current imported modules,
current social review APIs and all original driver statements remain unchanged;
only the already-approved exact actor literal substitution is served.

Current `customer_social_review.py` retains options, prepare/read and confirmation
routes. Reviewed API4 exercises those current routes without capability exemptions.
The closed UI source/auth/document/graph contract from v1 remains in force: genuine
retained source, current API, normal same-actor login/logout, exact workspace-name
change, precomputed current review and approval, unchanged financial/source rows.
Media remains current owned serving/decoding. Expiry uses the original test seam.
This is planning review confirmation, never execution approval or publication.

## Separate Current Route Browser Acceptance

Extend `test_current_advertising_history_browser.py` with a distinct two-DB social
route case; do not alter existing execution/optimization cases or shared driver.
Use its existing current source-only workspace, normal login, full history driver,
actual scoped API and foreign-session assertions. For this new case, Chromium
navigates to the real `/app/social-configuration` URL. The harness calls the actual
ASGI app/router, captures that HTML response, asserts200/text-html and exact bytes
of current `advertising-history.html`, then replaces exactly one history script URL
with the test driver URL and adjusts Content-Length. All other routes/assets/API
responses pass through unchanged. Label this instrumentation explicitly; it tests
actual route selection and current DOM/module/API behavior, not untouched network
bytes. No historical source or retained shell is used in this case.

The unchanged history driver checks no input/textarea/form, only read/refresh buttons,
actual empty owned history, session-change clearing and foreign-workspace denial.
Keep zero execution runs/attempts and its advertising-write request counter checks.
Do not claim the absent retained social action controls are current product features.
The two new history cases are supplemental coverage, not two additional recoveries
of the original four failures.

## Qualification After Review

First rerun only retained-shell SQLite Meta/TikTok gate; if the current component/API
fails, preserve the exact boundary rather than bypassing or falling back to old code.
Then four retained-shell cases plus two current social-history cases, bounded reviewed
API4/config positives/default boundaries. Do not rerun parent-owned historical action
or unrelated current-history packages unnecessarily. Whole Ruff/bare mypy/Node/diff
at final source. Use unique temporary basetemps and durable logs/XML/artifact copies.
No Full, shared DB reset, TTL change, live calls or production edits.

The earlier WIP remains unqualified and backed up; this docs commit does not certify
its implementation. All failures remain recorded. Parent review is required before
implementing this revised shell/history split.

## Approved Timestamp Correction During Qualification

The original ORM name assignment invokes `WorkspaceTimestampMixin.updated_at`.
The first retained-shell gate and one bounded diagnostic established that actual
login committed successfully, but the new recorder rejected its graph because the
proposed name-only delta omitted that automatic field. Preserve those failures.
The closed correction is one-shot `record_workspace_name_change` immediately after
the original commit: original owned name becomes the exact XSS test string and its
actual updated_at falls inside real UTC before/after commit bounds; every other
row/column stays exact. Freeze that resulting graph before login. Subsequent login
and final comparisons permit no further workspace changes. Copied timestamp/bounds,
name/other-column and second-binding negatives supplement the genuine browser flow.
No original baseline, DB timestamp, current clock or auth behavior is rewritten.
