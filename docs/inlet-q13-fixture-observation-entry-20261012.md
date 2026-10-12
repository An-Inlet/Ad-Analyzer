# Q13 Customer Fixture Observation Request And Recovery

Continues ac4b62ab on local `codex/inlet-w1-followup`. The assembled application had
budget history/receipt readers but no customer acquisition entry point. This package
closes that narrow offline gap. It does not activate or qualify live Google reads.

## Implemented Behavior

The [reviewed contract](design/q13-fixture-observation-entry-20261012.md) adds POST
`/api/customer/v1/workspaces/{workspace_id}/planning/plans/{plan_id}/budget-observations`.
The strict customer body contains only expected version/event sequence, document/action
binding and request key. The server supplies path scope and the pinned extraction
profile. CSRF, current owner/session, paid entitlement, goal/source/privacy, head/CAS and
final-authority checks remain in the existing service. No customer query, raw evidence,
account override or callable is accepted. No new invalidation endpoint or job was added.

`INLET_CUSTOMER_GOOGLE_BUDGET_OBSERVATION_MODE=disabled` is the default and example.
An offline harness must explicitly select injected_fixture, configure V6 and install an
immutable in-process GoogleBudgetFixture. One fixed tuple of bounded raw selected pages
is bound to workspace, privacy and the digest of the entire exact ExecutionAccount/source.
There is no network transport, credential handling, production mode or fixture upload API.
A setting alone cannot install a bundle. Acquisition gates run before each page and
before/after append; replacing the bundle or disabling the mode refuses. Historical
receipt/history GETs remain authorized and available after acquisition is disabled;
disabled POST, including replay, refuses.

The portal offers a separate synthetic-comparison control only for a current owned
Google DAILY shared-budget hypothesis and an advertised fixture capability. It requires
explicit acknowledgement and retains the exact request body/key across ambiguous
responses. The existing pending mechanism binds recovery to the original customer and
workspace; there is no automatic retry. Full event-envelope and actor binding checks
reject malformed results without discarding pending evidence. The historical event
validator is now self-contained, preserving its legacy renderer callers.

Fixture timestamps measure replay, not provider freshness. Results retain injected_fixture
provenance and not_assessed implementation/current reliance. A hypothesis match does not
verify customer implementation, spending-limit compliance, causality or improved results.
Customer application reports, immutable old versions and historical readers stay separate.

## Checks Actually Run

Frozen packet: `/workspace/inlet-evidence/20261012/q13-fixture-entry03/`.
Manifest SHA-256 `58fd1a6abd875471adbe59827867512fba673fcc8c3f8a4a59cd7a5e4b0840f4`.
All 28 commands passed, with 1,901 source hashes verified before/after execution:

- Whole-repository Ruff, configured mypy (1,584 files), exact collection and diff check.
- Two components: default-disabled/live-mode rejection and Chromium mixed historical
  document/event rendering.
- Eleven SQLite cases, then the same eleven PostgreSQL cases: six retained budget
  service/history/security cases; the existing V7 customer-report correction lifecycle;
  new assembled request/configuration-fence lifecycle; new actual HTTPS fixture browser
  journey; existing configured V6 positive browser; existing default V3 browser journey.

The new API case verifies disabled/missing bundle, wrong policy/source/privacy, viewer
and foreign-workspace refusal, CSRF and injected-field refusal; disable, bundle replacement,
policy change and identity revocation during acquisition; rollback when disabled after
both event/receipt inserts; successful observation, exact replay and changed-intent conflict;
and no-store receipt/history recovery with acquisition disabled. Advertising-read call
lists stay unchanged after generation and six execution/financial row counts remain zero.

The new actual browser case commits through the assembled API, rejects forged event
write authority in the POST response, preserves the pending key when a receipt response
is lost, rejects a forged receipt actor, then recovers the original event after runtime
disable. No second acquisition occurs, and a stale POST replay receives 503. The regular
V3/V6 browser cases remain passing. Existing service cases preserve revocation, erasure,
source fencing, immutable history/invalidation, exact event-CAS refusal, receipt recovery
and archive behavior; the separate V7 case protects customer-report correction semantics.

No skipped nodes, interruption, kill escalation, surviving child or source drift was
recorded. Process-duration sums: static 12.111s, component 18.511s, SQLite 430.433s,
PostgreSQL 461.347s. These are individual bounded checks, not capacity/availability claims.
`qualified-summary.json` binds 12 copied synthetic history/CAS/API/browser/route-observer
artifacts by hash; `prior-attempts.json` retains all original earlier results and unrun nodes.
No full-suite, hosted-CI or live-environment verification is claimed.

Earlier attempts remain intact: entry01 stopped at Ruff (import order, three long lines
and loop-variable binding); later checks unrun. entry02 passed Ruff then stopped at one
redundant mypy cast; later checks unrun. Those source issues were corrected before entry03.
There was no runtime failure or unchanged acceptance retry in this package.

Independent source review closed after fixing event-envelope/actor validation and avoiding
an inherited mutable nested account model. Final source/evidence/docs review is recorded
in the local commit binding. Documentation updates after qualification do not alter code.

## Concrete Launch Blockers And Next Package

1. Q13 is still synthetic and limited to one Google DAILY shared-budget hypothesis.
   Authenticated provider transport/provenance, live API-version qualification, broader
   proposed-field/partial comparisons and current-reliance assessment are absent. The
   new control is an offline harness path, not a supported production observation feature.
2. V3 remains the default. V6/V7 are selectable but release-unqualified. The generation
   reliability incident INLET-REL-20261012-01 remains open; this package neither diagnoses
   its original expiry nor supplies representative load/concurrent-generation qualification.
   Preserve the [bounded qualification plan](design/v6-concurrency-release-qualification-20261012.md).
3. The [six human usefulness judgments](inlet-owner-quality-gates-20261011.md) remain open.
   An owner/nominated ecommerce advertising expert must record per-case verdicts and
   corrections; automated passes are not those decisions. Q01–Q16 are not all complete.
4. Commercial terms and authorized live identity, payment, storage, provider setup,
   intended-environment operations and representative customer pilots remain release gates.
   Hosted-check authority/budget, reviewed merge and deployment remain separate approvals.
   Inlet is not yet a live-qualified purchasable release; the webpage stays owner-managed.

One coherent next offline package: define and implement a scoped read-only status projection
for retained budget observations across source changes and paginated invalidation history.
Report known source-generation changes, original evidence age and recorded invalidations
separately from the immutable finding; matching local source alone must never mean provider
freshness, implementation or live verification. Use existing retained proofs and current
authorization, no provider call or automatic history rewrite. Qualify request/history recovery,
revocation/erasure and browser states on both databases. Review that shared interface before
implementation; keep the synthetic acquisition mode disabled by default.

No push, PR, hosted CI, merge, deployment, live provider/model/payment call, credential
operation, customer advertising change or spending occurred. The local branch and commit
binding are the reviewable delivery; all owner/release/incident restrictions remain.
