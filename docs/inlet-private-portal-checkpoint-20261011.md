# Private Planning Portal Checkpoint — 2026-10-11

Integrated production source: `226841a` on `codex/inlet-w1-followup`.
The private selected-event/creative portal adds product facts, exact prices,
restrictions, explicitly uploaded owned PNG/JPEG images, saved creative basis and
session-fenced previews. Per-field editing preserves untouched saved values exactly.
Independent source review is closed. Default V3 remains unchanged; V4/V5 identify
internal policy contracts, not product completion or live activation.

Component/CSP qualification: four passed; the subsequent field-preservation repair:
two passed. Author and root whole-repository Ruff and configured no-path mypy pass
(1,412 files). These checks do not replace authenticated browser qualification.

## Browser Qualification Remains Incomplete

Evidence: `/workspace/inlet-evidence/20261011/creative-portal-browser/`.
`both-02.xml/log` stopped after four SQLite passes and one PostgreSQL Google
first-generation HTTP 409, with seven cases unrun. The generic portal conflict
message did not retain its exact server detail. Its cause is unknown. A subsequent
single-case PostgreSQL diagnostic passed with two HTTP 200 generation responses;
it does not resolve or explain the failed cohort. Both attempts remain retained.

The seven previously unrun cases subsequently passed in `remaining-04` (120.261s)
with bounded status/error-detail/elapsed capture. The isolated PostgreSQL diagnostic
passed in 42.332s. All twelve distinct cases now have passing observations across
separate attempts; the original five-case attempt (95.039s, one failure) remains
unresolved. No fresh whole-cohort success is claimed.
Independent source review found a safety-test ordering gap: cleared editor assertions
could execute before replacement login and late response completion. The safety
observations were superseded by strengthened completion assertions and targeted
both-database qualification: `safety-05` passed both cases. Independent source review
accepted the synchronization repair. This was an evidence gap, not an established
production defect.
A single instrumented PostgreSQL Google diagnostic (`stage-06`) subsequently passed.
Maximum sampled fact ages were 3.583s and 3.946s; save-generation intervals were
3.582s/3.946s with 2,276/2,293 SQL calls. Nested stage timings overlap and must not
be summed. This measures current costs without explaining the original 409.
The separate single SQLite `capture-07` journey passed. Root inspected the actual
PNG pixels: saved product price USD 25.000000, one PNG, original observation and
rights/claim/unassessed notices are legible; the Google action shows selected count
10, 100 clicks and USD 100 spend. No visual defect was seen at that captured
viewport. This is neither an expert-quality nor mobile/rights approval. No
full-cohort retry is claimed.

The separate API `final06` failure did record `planning_authority_expired`.
Successful API timing observations before/after query reduction measured maximum
fact ages 2.759s/3.693s and SQL counts 2,627/2,217. This establishes a reduction in
queries, not a latency improvement or the browser failure's cause. The normal
28-case API cohort subsequently passed; all prior failures remain in its ledger.

Independent review recommends observational request-stage timing, measured against
the original identity fact, before proposing a production change. Preserve the
five-second limit, fresh selected/image/selected proofs, transaction guards and
post-flush checks. A potential pure-validation preparation optimization needs its
own immutable ownership contract and supporting measurements; it is not approved
by this checkpoint.

## Remaining Release Evidence

All six [human quality gates](inlet-owner-quality-gates-20261011.md) remain open,
and Q01–Q16 remain partial. The [actual artifact review packet](inlet-creative-review-packet-20261011.md)
is available; it contains synthetic review material, not expert verdicts. Live
identity/payment/storage/provider activation, commercial decisions, pilots and
human merge/deployment gates remain. There are no new remote pushes or hosted runs.
The frozen qualified `9d7aa2e` evidence is unchanged and does not qualify this head.

## Integrated Browser Freeze

Root integrated browser commit `5aa82b3` is the unchanged cherry-pick of reviewed
`87c44be593a771c78715f837cab0ae516ca6368b`. Independent final source/evidence review
is closed with no remaining P1/P2. Root whole Ruff and configured no-path mypy pass
on the combined branch (1,414 files). [Exact browser ledger](inlet-creative-portal-browser-package-20261011.md)
records all attempts, durations, screenshot provenance and limitations. This review
closure does not resolve the original PostgreSQL conflict or qualify a release.

Next package: a design-only performance proposal grounded in measured stage costs,
then independent contract review before implementation. No additional broad test
retry, authority renewal, relaxed freshness or live activation is authorized by
this checkpoint.

## Diagnostic Scope Correction

Further harness review corrected an earlier inference: the failed browser
**Generate action** performs POST generate, GET current plan, then GET version
history, and maps any HTTP 409 to the same message. The original `both-02` run
captured none of their statuses/details. Therefore the evidence does **not**
establish that POST generate failed or that authority expired. Its disposable
schema was cleaned up by the fixture, so no original database state survives.
Earlier references to a "generation 409" describe the user action only. Retain the
failure without attributing it to a particular route. The next bounded diagnostic
must capture fixed route classes/status/error detail for all three requests.
