# Fresh-Brand Offline Customer Journey — B20 Proposal

Baseline dc3c0d5, isolated inspection worktree /workspace/inlet-fresh-brand-pilot.
This is a bounded integration proposal, not a live pilot or approval to alter flows,
financial gates, configured offers, provider grants or production runtimes.

## Concrete Gap At This Baseline

The current suites prove substantial real behavior, but begin at incompatible
bootstrap points and do not establish a fresh customer's cross-feature continuity:

- `test_two_brand_pilot.py` creates real identities/workspaces and uses goal/review
  APIs, but installs native advertising connections and Shopify baselines directly;
  its creation/activation stages call coordinator services. The matrix correctly
  calls those fixture boundaries. Its remaining-API wording is now historical:
  customer execution and session-control pages exist, and should not be relisted
  as absent code.
- `test_customer_browser_api_journey.py` starts through visible sign-in/provisioning
  and real Shopify/API/import/goal behavior, with provider seams mocked. Its billing
  transport is FixtureBilling and its scope does not continue through advertising
  OAuth, campaign review or session automation status.
- `test_billing_browser_journey.py` verifies actual Stripe test HTTP and external
  navigation/return/recovery, but seeds the initial workspaces/session and uses the
  legacy test billing scope. The immutable offer and environment-separated billing
  tests exercise newer bindings separately; no fresh browser composition verifies
  that paid evidence remains bound to the same newly provisioned workspace.
- Google/Shopify/CRM consent browsers exercise actual controls and callbacks in
  separate fixtures. Campaign review/execution/session-automation browser fixtures
  start with prepared source/goal/account/mandate state rather than carrying the
  freshly created owner's rows through those transitions.

Thus the missing evidence is continuity of one real application's customer,
workspace, paid scope, connected tools, imported baseline and exact draft approval
across page navigation/reload, with truthful unavailable automation. It is not
another rendering test or a reason to replace the existing per-page tests.

## First Bounded Journey

One fresh synthetic Shopify brand, one fresh unrelated second identity/workspace
for denial checks, one disposable database, one assembled app, separate browser
contexts. Run on SQLite and PostgreSQL with unique schemas. No precreated customer,
workspace, subscription, goal, native connection, source fact, campaign draft,
mandate, approval or session-automation row for Brand A.

1. Visible sign-in using the existing fake identity-provider SDK boundary; actual
   server session cookies and CSRF, then visible idempotent workspace provisioning.
   Reload/navigation must retain only the authorized workspace.
2. Open configured **test** checkout through existing controls and actual
   settings-backed test billing adapter with MockTransport and a synthetic approved
   immutable offer. Intercept the Stripe-hosted navigation with an explicit offline
   provider page, then return through the actual app URL. A return alone must not
   grant entitlement. Deliver a signed synthetic scoped webhook and run the real
   receipt/reconciliation path. Verify entitlement and offer binding belong to the
   new workspace and test billing environment. Do not use a blanket paid flag or
   direct WorkspaceBilling seeding. Determine whether the current test checkout
   factory supports the immutable configured offer before implementation; if not,
   document the concrete boundary and use the existing supported test offer path
   without claiming immutable-offer integration.
3. Through real portal controls, authorize/select a Google account and connect
   Shopify. Provider consent/navigation/token/metadata boundaries are mocked, with
   actual OAuth state/session binding, vault storage and account ownership. Reuse
   existing fixed-provider HTTP fixtures rather than inventing new resource claims.
4. Invoke the normal bounded commerce import worker explicitly as test orchestration
   (not a new customer button or automatic scheduler). Its actual collector and
   ledger code produce the baseline from synthetic Shopify responses; no fact or
   coverage rows inserted directly. Expose this worker trigger only in the harness.
5. Use the existing structured goal editor, preview and exact confirmation. Assert
   the confirmed revision references Brand A's imported store/currency/timezone and
   budget. Current UI does not supply the requested free-form milestone journey;
   this test must record the structured-editor boundary rather than fabricate one.
6. Navigate to campaign draft creation/review, use supported supplied Google Search
   content, and approve the exact current draft revision. Assert it carries the
   same confirmed goal/native owned account and remains an offline content approval,
   not publication/activation consent. Keep the upcoming total-budget UI entirely
   outside this package until its independent frozen consumer is integrated.
7. Navigate to Account Diagnostics and perform the actual read-only assembly through
   vault and MockTransport. Paid access, selected account and current session must
   survive the navigation. Result stays unqualified with optimization unavailable.
8. Visit Existing Campaigns/Session Automation. With production policy/runtime
   defaults absent, show truthful unavailable state and no Start/admission/provider
   mutation. A paid subscription, connected account and confirmed goal must not
   manufacture spend authority. The separately qualified seeded automatic-worker
   tests remain separate evidence; this journey will not inject a runnable policy
   merely to pretend the fresh customer can automate.
9. Sign out and sign in as Brand B. Brand A data disappears from all active selectors;
   direct remembered A goal/draft/diagnostic reads fail without provider calls. Brand B
   can provision its own workspace. A fresh A session can recover its own persisted
   goal/review/billing status, with no replayed checkout or provider mutation.

## Shared Fixture Boundary

A new `FreshBrandHarness` owns only: HTTPS server/browser launch, disposable DB
sessions, deterministic clock, explicit low-level HTTP/provider SDK mocks, signed
webhook delivery and bounded worker advancement. Browser actions create customer
state; test inspection may read rows but must not repair or seed missing customer
state between stages. All mutations/HTTP calls are recorded as counts plus safe
operation names; no tokens, native response dumps or DSNs in logs.

Extract small reusable mock transports/browser navigation helpers from existing
suites only if necessary; do not refactor unrelated production code. Keep provider
and billing scope interfaces unchanged. The proposed scenario should fail if a
stage changes workspace/identity/environment, grants paid access merely on redirect,
uses a stale goal/draft, leaks foreign rows, or enables default automatic execution.

## Exclusions And Acceptance Meaning

No live purchase, real business, actual provider consent, imported customer data,
production qualification, independent mature feedback or advertising effect is
claimed. No publication/activation is required for this first bounded fresh-brand
slice while production native financial/evidence/runtime gates remain unresolved.
No new product behavior or migration is proposed. A passing result closes only the
identified fresh-customer cross-feature read/review/blocked-execution evidence gap;
B20 unrelated live pilots and the full working SaaS acceptance remain incomplete.

Recommendation: implement this one coherent scenario after the immediate reviewed
Google total-budget UI package. If real composition exposes a missing feature,
report its exact boundary rather than patching it with direct DB setup or silently
changing gates. Root review of this proposal precedes implementation.

## Implemented Offline Evidence

The approved prototype found the missing visible planning-budget creation/approval
step. A narrow Plan Review page and canonical timezone context now expose the existing
simulation APIs. No customer/goal/native connection/mandate/draft/approval rows are
seeded in the fresh journey. Synthetic provider responses and real configured local
private-media storage are test infrastructure only. The test billing factory consumes
an immutable test-scoped offer, actual Stripe adapter/HTTP validation, signed webhook,
and actual reconciliation. Return navigation alone is asserted insufficient.

The browser carries the same fresh workspace through Google and Shopify OAuth/vault,
the actual Shopify commerce import, structured goal preview/confirmation, planning
budget review, exact Google content approval, account diagnostics, truthful unavailable
automation, logout, foreign-brand denial/provisioning, and original-brand recovery.
No production execution approval, provider execution attempt or automatic admission
is created. Existing paid access and offline reviews do not grant spending authority.
Google is connected and its native inventory is read; this test does not claim a
Google campaign-metrics import or mature performance learning.

The remaining free-form milestone interpretation, qualified production optimization,
actual publication/activation, and live unrelated customer pilots are not established
by this offline test. These are boundaries, not test fixtures to be filled with fake
proof. See the progress ledger for exact checks and revision.
