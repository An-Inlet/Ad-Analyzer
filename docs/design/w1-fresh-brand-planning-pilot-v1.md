# W1 Fresh Brand Pilot: Historical Preservation And Current Planning Journey

Proposal only. Base `608c7f5`; inspected 2026-10-10. No implementation, test run,
source extraction, remote operation or product behavior change is included.

## Coverage Contract

Preserve the **entire original** `tests/test_fresh_brand_pilot.py` journey under
exact PIN2155ff3 using the existing bounded historical runner/identity manifest
conventions. Preserve original assertions, parameters and both database identities;
record source/AST hashes and terminal child XML. Do not replace its later stages
with an early planning-boundary denial, a no-source snippet or a detached shell.
The historical run proves the historical product only. Do not turn on retained
execution in the current application or use historical cookies/rows as current
onboarding authority.

Add a separately named current planning journey, proposed
`tests/test_fresh_brand_planning_pilot.py::test_fresh_visible_planning_brand_journey`,
with SQLite and disposable PostgreSQL variants. Both current cases start empty;
they are supplemental current acceptance, not two extra original failure identities.
The two original aggregate failures remain open until reviewed historical evidence
and the agreed current journey are terminal. Root owns the immutable coverage overlay.
Current ledger is 1280/1330 covered, 50 remaining; this proposal changes neither.

## Shared Fixture Boundary

Use real HTTPS Chromium navigation to unmodified current public shells, real customer
API routes, persisted identity/session/workspace ownership, billing dispatch,
connection callbacks/vaults, commerce imports, goal confirmation and planning service.
Start with zero customers, workspaces, memberships, connections, goals, plans and
execution effects. No pre-provisioned `setup_evidence`, ready plan ticket, direct
plan/goal/account insertion, fake evidence bundle or patched service authorization.

Allowed substitutions are narrowly external: synthetic identity SDK/provider,
local Stripe HTTP/test checkout consent surface and signed webhook, Shopify HTTP
consent/token/shop/order/agreement responses, Google OAuth/token/account discovery
and fixed read-only native/report responses. Route all provider traffic to bounded
local mocks; unexpected requests fail. Invoke real due worker/import entrypoints
explicitly instead of sleeping for a scheduler. Record exact substituted ports and
synthetic granted scopes; do not imply a real historical Shopify grant or live payment.

Reuse `FreshBrowser`, HTTPS certificate/browser isolation and billing lost-response
patterns only after separating helpers from collection safely. Configure current
planning policy, not legacy execution flags. Use fresh real-time-compatible clocks
across browser/server/callback signatures, closed account-local report days and
store-local goal months. Do not extend source/session TTLs merely to pass a slow run.
Provider time and worker timing may be controlled explicitly; final security clocks
remain as production defines them. The chosen store/account zones must be explicit;
a second DST-crossing case can be a focused companion if full journey cost warrants.

## Exact Visible Journey And Assertions

1. **Identity and workspace.** Open `/app`, sign in through the ordinary SDK/token
   exchange, create Fresh Brand through the visible form. Assert one owner membership
   and one selected workspace; no preexisting user or fixture account is used.
2. **Test purchase and recovery.** Click configured test checkout; drop the first
   provider response after it records the request. Status refresh must not POST.
   Explicit Resume uses the original offer/idempotency key. Returning from checkout
   alone must not grant entitlement. Deliver the signed synthetic test event and run
   the real billing dispatcher; visible Active and persisted test entitlement must
   agree. State clearly that this is not a live purchase. Avoid claiming planning
   payment enforcement where the current service does not explicitly impose it.
3. **Owned read connections.** Connect Google through OAuth callback and named account
   selection, then reconnect the same account and prove no duplicate ownership.
   Connect Shopify through its signed callback. Run real commerce collection and
   required measurement publication from mocked provider pages, with completion and
   source lineage verified. Any Google reporting checkpoint required by the current
   planning evidence reader must come from its actual importer, never inserted
   DailyMetric/CurrentPerformance rows. Native search POST is a semantic read, not an
   advertising mutation; count it separately from forbidden mutate endpoints.
4. **Milestone, editable goal, confirmation.** Use current workspace goal controls;
   enter an explicit sales target, target month, baseline month, currency, budget
   dates/ceiling and aggressiveness. Edit target from 10000 to 12000 before confirming
   the exact revision. Assert persisted value, currency, store-local boundaries,
   budget/aggressiveness and confirmation match the displayed version. If baseline
   coverage is incomplete, assert the actual warning; do not invent historical sales
   or require a readiness label unsupported by the imported source.
5. **Current planning entry.** Follow the visible Your Advertising Plans link to
   `/app/planning`; do not route through simulation approval or `/app/optimization`.
   Choose the owned confirmed goal and named Google account. Assert the goal summary
   carries the exact confirmed ceiling/aggressiveness; editing those values requires
   goal edit and reconfirmation, not a second invented financial consent.
6. **Plan inputs and useful evidence.** Supply milestone/product facts, constraints,
   assumptions and closed reporting days entered as explicit UTC instants matching
   the account zone. Read current native targets and select a named target. Save
   inputs, generate a version via actual API/service/evidence composition, then read
   it. Assert owned source references and exact input/version commitments, readable
   evidence and manual instructions, explicit missing/unsupported evidence, and
   `advertising_writes_enabled=false`, `spending_authority=none`. Optional allocation
   must stay inside the confirmed ceiling; do not require a recommendation quality
   or campaign-specific result the composer cannot actually support.
7. **Review and customer application report.** Record acceptance of the exact displayed
   version/action using the confirmation control. Record a separate synthetic
   customer-reported application and verify history labels distinguish it from
   independent verification. No ad is changed by either action. Revise a constraint,
   generate/read the next version, and verify an old version/action cannot silently
   become the newly selected review. Preserve request-result recovery after one
   deliberately lost planning mutation response: read receipt first, no automatic
   resend or duplicate input/version/event.
8. **Observed progress.** From the selected plan read Sales Progress and from workspace
   read goal progress. Assert exact merchandise-sales definition, store currency,
   source/as-of/coverage and the edited goal reference. Use real new synthetic commerce
   input through the importer for any change assertion. Incomplete/current-month
   coverage stays explicit; no attribution, causal lift, settled outcomes or verified
   customer application may be inferred from increasing sales.
9. **Isolation, logout and restoration.** Sign out and sign in as a second fresh
   identity. Its empty selector must not reveal the first brand. Probe first-brand
   goal, planning document/version/events/export/progress and owned account reads
   with the ordinary browser API helper: deny without private payload or provider IO.
   Create the second workspace through UI; then return as the original customer and
   recover persisted billing, exact goal and plan/history through normal reads.
   Revoke the original persisted session as an adverse test control; next progress
   read must deny and clear displayed private content with no new native IO. Include
   missing/foreign CSRF denial for a current planning mutation without creating rows.
10. **No effects.** At relevant stages and final teardown assert zero execution
    approvals/attempts/admissions/new held reservations and zero advertising mutation
    requests. Old execution URLs render their actual current history/boundary behavior;
    never restore old Start, publish or activation controls to satisfy this test.

## Current Source Map And Concrete Acceptance Risks

- `tests/test_fresh_brand_pilot.py`: full zero-user legacy journey, real mocked
  connection/billing/import prefix and identity/progress suffix; its Plan Review,
  campaign and optimization middle is not the new planning acceptance contract.
- `app/portal/static/index.html`: visible `/app/planning` entry exists, but also still
  links Plan Review and Campaign Review. `plan-review.html` advertises saving and
  approving a simulation. Verify their current unavailable behavior separately;
  exposing controls that lead only to write-prohibition errors is a usability gap,
  not authority to restore those APIs in this pilot.
- `app/portal/router.py`: `/app/optimization` now serves Advertising History;
  `/app/planning` serves the actual planning shell.
- `app/portal/static/planning.html`, `planning.mjs`, `plan-document.mjs`,
  `plan-events.mjs`, `plan-progress.mjs`: current budget inheritance, generation,
  version review, manual reporting, recovery and progress controls.
- `app/api/customer_planning_catalog.py`, `customer_planning_documents.py`,
  `customer_planning_target_catalog.py`: owned current interfaces. The current
  `/planning/accounts` catalog does not require an execution mandate.
- `tests/test_planning_documents_browser.py` and
  `tests/test_planning_evidence_adapter.py`: valuable current coverage but start
  from provisioned sources/goals. They do **not** establish that a newly OAuth-selected
  Google account plus real import becomes usable planning evidence. That composition
  is the central open integration risk; report a concrete failure rather than seed
  around it or weaken source completeness/freshness.
- The planning UI asks customers to translate account-local closed days into UTC;
  preserve timezone/DST correctness and document this actual usability limitation.
- Current UI explicitly says recommendation quality is not expert-qualified. The
  journey must not silently relabel a descriptive or insufficient plan as a useful,
  financially qualified recommendation. If only an insufficient document is possible
  with complete supported fixture evidence, surface the exact missing producer or
  composer behavior as a product blocker before claiming pilot success.

## Implementation And Evidence Gate

After review, freeze helper ownership and actual current reporting/import ports with
their owners before coding. Implement the current journey separately, then add the
exact historical two-node manifest through the existing registry owner. Run only
bounded targeted SQLite/PostgreSQL cases and necessary static checks, with terminal
XML/logs and actual source/mock boundaries. No aggregate, hosted run or remote write.
A failed stage stays a failing acceptance finding; no broad retirement, assertion
relaxation or fabricated source. Do not delete the original test before immutable
preservation and identity mapping are verified.

Disk preflight observed 585 MiB available before this docs-only worktree. Require at
least 500 MiB again before extraction/browser/testing; if insufficient, stop heavy
work and coordinate cleanup of regenerable caches only. Preserve unique evidence,
source, databases and media. No cleanup was performed here.

Website remains paused/owner-managed. All Q packages remain partial; all six human
release gates remain unmet. Neither historical nor mocked current acceptance is a
live pilot, purchase qualification, deployment approval or finished SaaS claim.

## Additive Fixture Interface Freeze — 2026-10-10

Implementation owner: customer_portal owns the new current pilot test/fixture and
this document; imports `FreshBrowser` and `TestOfferHTTP` by explicit class name
from the legacy module, never its collected test function. Historical manifest and
coverage registry changes are coordinated with root; append only this package's
exact two PIN2155 children, not rerun previous batches. Shared production/importer
files remain read-only unless a reproduced defect is separately coordinated.

Concrete producer ports: Shopify uses actual customer authorize/callback routes,
`CommerceSyncService.page(wid, now=reporting_clock)` and its existing terminal
measurement publication. Google uses actual customer authorize/callback/select,
`google_connections.contracts.get_transport()` with only HTTP transport injected,
and `google_connections.service.tick(db, wid, cid, generation, transport, now)`; its terminal
`campaign_performance.aggregate.publish` remains untouched. Native target reads use
`account_diagnostics.diagnostic_transport` with MockTransport. Planning uses default
`PlanningDocumentService` v3 and `OwnedPlanningEvidenceReader`; no v1/v2 policy
substitution, fabricated completion or expected-success bundle. If current v3 does
not support the resulting genuine Google completion, record the exact gap and
retain truthful insufficient output; do not claim supported complete evidence.

Temporal fixture: use real UTC now for identity/session/callback validation and
planning freshness. Set provider reporting to the immediately preceding complete
UTC day (Google account zone UTC); Shopify shop zone UTC, baseline previous complete
calendar month, goal target next calendar month and budget exactly that target
month. Use an explicit synthetic September/November2026 legacy clock only inside
the isolated PIN test, never current planning authorization. Current Shopify source
and agreement dates are generated relative to the declared reporting/goal windows;
all acquisition completion timestamps are actual importer values. OAuth expires_in
stays3600; no session/native/plan TTL extension. First gate is SQLite actual fresh
connection→import→confirmed goal→default planning generation, before the broader
both-DB browser/recovery/isolation matrix. Capacity preflight before implementation
read533MiB; repeat immediately before any browser/extraction run.
