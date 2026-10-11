# Private creative planning portal — actual browser qualification

This test-only package targets the reviewed private portal interface and its frozen
DOM contract. It does not enable a new customer default, change production service
configuration, or confer advertising execution permission.

## Customer journey and fixture boundary

The final harness retains the actual /app/planning response and its CSP headers,
replacing only the test entry module. It does not relax image or script policy.
The actual TLS browser enters a declared product and exact retail price, uploads
and selects the tracked synthetic mug PNG through the real media API, previews its
owned bytes, saves planning inputs, requests a plan, reads the retained image/product
basis and downloads the server's version artifact using the portal button. Google
also exercises an actually committed save whose response is lost, recorded-result
recovery without a duplicate POST, editing retained product/image values, a successor
plan and exact original export. After local bytes disappear, historical export
remains exact and a current preview must fail honestly. Metadata currentness does
not assert that current bytes remain accessible.

The source fixtures are acquired beforehand through actual owned APIs and services,
with only provider wire IO mocked. Chromium then establishes a **fresh actual
session for the same owner** and retains that original session throughout its
positive upload/save/generate/export journey. Its input save acquires any required
session-bound catalogue receipts normally. This is not a claim that pre-browser
source acquisition and browser actions share one session; the preceding API Common
Basis package separately tests the complete same-session API path.

The trusted test server configures the genuine private service and the same private
MediaStore for upload/generation. No plan, evidence, proof, receipt or execution row
is seeded, and no ready-made service result is injected. A second owned workspace
is only a foreign-access fixture, never a positive plan source. There are no changed
authentication clocks, live provider/model calls or screenshots.

Meta and TikTok journeys show the same customer-declared product/image while
retaining unsupported reporting gaps. TikTok's three-shot storyboard is a production
proposal, not an existing owned video. Displayed image observations retain their
original timestamps and explicit unassessed language. No visual-suitability,
commercial-rights, causal-performance or expert-quality claim follows.

## Bounded acceptance matrix

- Google: actual selected reports plus product/image create/recovery, generation,
  visible basis, real download, edit/successor, immutable history and missing-byte
  preview failure.
- Meta: actual partial owned catalogue, explicit reporting gaps and product/image
  production instructions through the portal.
- TikTok: actual regular campaign/adgroup catalogue, unsupported selected reporting
  and explicit video-production instructions without an owned video.
- Safety: actual foreign-workspace media denial, undecodable image upload with no
  optimistic selection, and late real library response across same-owner session
  replacement clearing scoped controls with no saved plan.

Each runs on SQLite and isolated-schema PostgreSQL (eight cases). Four unchanged
legacy-v3 documents and v4 selected browser cases preserve earlier journeys. Fine
field/size/hash/order permutations belong to the separate component tests and are
not duplicated here. Execution, attempt, approval and reservation counts remain
zero. First generation may perform read-only native acquisition; none is described
as advertising mutation.

## Evidence

Qualification logs and result records are retained under
`/workspace/inlet-evidence/20261011/creative-portal-browser`. Final counts, commands,
production dependency and any observed failures will be appended after tests.
Initial SQLite Google and safety journeys passed on the first production freeze.
The final matrix waits for the separately owned per-field preservation repair;
the initial journeys do not qualify that repair. Exact final results follow.

### Retained first qualification results (not final closure)

- `sqlite-01`: Google and safety journeys passed on SQLite before the independent
  per-field preservation repair (2 cases). No CSP browser claim is attached to
  that first harness version.
- `both-02`: repaired UI plus actual-page CSP harness, stopped at first failure:
  four SQLite journeys passed; PostgreSQL Google generation returned409 and its
  portal message reported changed plan/source/selected snapshot. The original
  fixed server detail was not captured. Seven remaining cases were not executed.
- `pg-diagnostic-03`: added test-only bounded generation status/detail capture;
  the one PostgreSQL Google journey passed, with both generation responses200.
  No production, clock or authority change was made. This isolated pass does not
  diagnose or close the preceding cohort failure; stage timing is still needed.

The stopped-cohort XML/log and successful SQLite result records remain retained,
as do the isolated diagnostic XML/log and its status-only records. No repeated
full matrix or screenshot run is claimed. Screenshot capture was deferred at this checkpoint; the later separately approved
capture is recorded below. No auth/network/Runtime traces exist.

### Remaining cases and strengthened safety qualification

`remaining-04` completed all seven previously unrun cases: seven passed, zero
skips/failures/errors, 120.261 seconds. These include Meta/TikTok/safety PostgreSQL
and the four unchanged v3/v4 browser journeys. This is not a complete-cohort retry
or a resolution of `both-02`.

Independent review found the first safety synchronization could inspect an
already-hidden editor before replacement login completed. Earlier safety passes
are therefore weaker observations, superseded by the targeted strengthened test.
The repair requires a busy controller, actual successful replacement login and
changed cookie, delivery of the original library Response, then a settled
controller with session-change feedback and cleared controls. It neither requires
body parsing (the correct cookie fence rejects earlier) nor adds a fixed wait.

The evidence-only diagnostic source is retained outside the repository beside the
logs. It observes the actual generate service and delegates, calls originals once,
and preserves every exception. Stage durations overlap and cannot be summed;
authority age is sampled at guard entry. It logs no request bodies, SQL text,
parameters, cookies, credentials or auth traces. No production repair is inferred.

### Targeted repaired safety and observational diagnostic

- `safety-05`: strengthened safety journey passed on both databases, zero skips,
  failures or errors, 14.749 seconds. This supersedes the weaker safety assertions.
- `stage-06`: exactly one PostgreSQL Google journey passed, 44.211 seconds. No
  production/gate/clock change. The two generation totals were 12.926/12.952 seconds
  with 8079/8113 SQL calls; `save_generation` was 3.582/3.946 seconds with 2276/2293
  calls. Maximum sampled fact ages were 3.583/3.946 seconds. These are overlapping
  observed stage costs, not an explanation of the original409 or a latency claim.
- The actual displayed Google count assertion now extracts the entire bounded
  number and accepts exactly ten (including trailing decimal zeros), not100/10.5.

All twelve distinct planned cases have now passed across the recorded runs, but
there is no single all-green twelve-case cohort and the first PostgreSQL409 remains
unexplained. No failing record was removed or recategorized. Default-v3 behavior and
legacy-v4 journeys remain exercised by their unchanged tests.

The optional capture helper is off by default. Its single approved synthetic
Google SQLite journey enables ephemeral loopback CDP in a temporary browser
profile, calls only `Page.captureScreenshot`, and saves only a rendered PNG at the
already verified saved-basis state. It neither enables Network/Runtime tracing nor
captures authentication state. This visual artifact is separate from functional
qualification and cannot establish visual suitability or expert approval.

`capture-07`: one Google SQLite journey passed, zero skips/failures/errors, 24.093 seconds. The durable `google-saved-creative-basis.png` and
`screenshot-manifest.json` contain the rendered artifact and SHA-256/provenance.
Pixels were inspected: saved product/price/image metadata and unassessed boundaries
are visible. No claim of visual suitability is made. The earlier409 remains open.
Root also independently inspected the PNG pixels: legible saved basis, exact
USD25.000000, one128×128PNG, original observation and unassessed/rights notices;
the lower manual action shows10selected events/100clicks/USD100. No rendering defect
was seen in this viewport. This is not mobile/expert-quality or rights approval.

Final static checks: whole `ruff check .` passed; configured `mypy` passed for1414
source files using a scratch cache; Node syntax and `git diff --check` passed.
All files in this commit are tests or this ledger. Production dependencies are
1d7b313 plus per-field preservation repair5a08ffe, each cherry-picked unchanged.

Reproduction: use the existing `customer_engine` fixture's isolated-schema local
PostgreSQL mode with the explicit disposable marker; commands/case IDs are retained
in the XML/log files above. No database resets or external network were used.
The screenshot additionally requires `INLET_CREATIVE_BROWSER_CAPTURE=1` and is
restricted by assertion to the Google SQLite journey. Diagnostic reproduction loads
retained `inlet_v5_browser_timing.py` with pytest `-p` on its evidence PYTHONPATH;
its SHA-256 is0ea59228eb05ac45e8d4856d8729875343dfa6ba7a359e9690b87095af023336.
The untouched predecessor probe is retained as `original_v5_timing_plugin.py`.

Remaining blocker: original `both-02` PostgreSQL409 has no captured fixed detail
and no proved cause. Subsequent passes and observational timings do not resolve it.
No blanket all-green cohort, default-v5 activation, live advertising, expert
quality assessment, or full Q01–Q16 acceptance is claimed.

### Correction to original route inference and ordered diagnostic

The original generic409 occurred during the Generate **user action**, which calls
POST generate, GET current plan and GET versions. The old harness captured none of
their statuses; prior wording “generation returned409” was an unsupported route
inference. The original cause and route remain unknown. Failed PostgreSQL schema
was dropped by normal fixture teardown; server/browser streams were discarded.
No authentication-bearing browser profile was inspected. A detailed source-site map
is retained in evidence `original-409-analysis.md`.

The independently reviewed route observer now captures only those three fixed
route classes, ordinal/status/allowlisted fixed detail/elapsed, at most100 records
and8192 transient error bytes. No identifiers, auth data or success body is retained.
It forwards the original ASGI messages unchanged. Unknown error text is redacted.

`ordered-08` ran the original order once: four SQLite journeys, then PostgreSQL
Google, with -x and no stage plugin or screenshot. All five passed, zero skips,
failures or errors,73.511 seconds. All observed route responses were200, including
both PostgreSQL generation requests and subsequent current/history GETs. Durable
XML/log and fixed records are retained. This does not explain the original409;
no immediate retry or production repair followed. Diagnostic costs are not a
performance benchmark or a substitute for future integrated qualification.
Observer successor static checks: whole Ruff passed; configured mypy passed1415
source files; diff check passed. No production changes or additional pytest runs.
