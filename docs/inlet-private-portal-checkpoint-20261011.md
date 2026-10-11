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

The seven previously unrun cases are being executed separately with bounded
status/error-detail/elapsed capture. No fresh whole-cohort success is claimed.
Screenshot capture is deferred while the functional conflict is investigated.

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
