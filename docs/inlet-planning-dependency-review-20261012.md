# Planning MVP Dependency Review — 2026-10-12

Baseline clean `8eb68c4`, branch `codex/inlet-w1-followup`. This is a source/evidence
review, not an exhaustive rerun or a claim that every historical backlog item passes
at this head. October 7 planning-only scope supersedes old execution priorities:
customers manually apply changes; no advertising-platform writes. Public website is
owner-managed. Existing live, credentials, payments, hosted CI, push and release holds
remain. V6 is default-off/selectable but not release-qualified; incident
INLET-REL-20261012-01 stays open.

| Planning Package | Repository Evidence Inspected | Actual Remaining Dependency / Priority |
| --- | --- | --- |
| P01 Write prohibition | Planning deployment boundary and October 8 assembled 183-case ledger; retained execution paths remain gated | Preserve boundary; no new execution work or activation |
| P02 Foundation / coherent journey | B01 positive/zero regression; identity/scoped membership/revocation in `test_customer_identity.py`; real signup/repeat/workspace/session tests in `test_customer_signin.py`; portal goals, owned connections and confirmation | Implement billing-only read recovery below. Real IdP/CSP/cookies, provider grants and uninterrupted live onboarding remain externally unverified; signup/provisioning APIs are not missing |
| P03 Useful comprehensive plans | Actual v3 default plus explicit v4/v5 composition, source-bound counts, product/media briefs, budgets/constraints and Q01–Q16 artifact ledger | Six expert usefulness judgments remain; v6 reliability qualification remains open. Generic freeform constraints still defer creative rather than produce useful constrained briefs; that is a separate typed-interpretation design/code gap, not permission to discard constraints |
| P04 History / recovery / outcomes | Version/export/decision/report/currentness/progress and erasure paths; Q11 corrections, Q14 identity reselection and later unknown-parent joins | Qualified independent field-observation producer/customer route remains a concrete Q13 engineering gap. It needs an exact proposed-field/source comparator contract and cannot turn investigation-only hypotheses or customer reports into verified edits. Reconnect history retention remains an owner decision |
| P05 Read integration parity | Google exact selected reporting and Meta count handoff; Shopify measurement; optional Klaviyo/HubSpot/Omnisend connector code; TikTok pure count parser | TikTok completeness needs authoritative provider semantics. Unknown attribution/value/custom-event meaning is not fixed by credentials. Live three-platform/commerce/customer-data qualification remains separate |
| P06 Billing / security / operations | Offer bindings/qualification, paid-invoice entitlement, production assembly denial, unknown-checkout GET recovery, repurchase and browser management tests; scoped lifecycle/export/restore evidence | Concrete billing UI recovery gap is ready now. Offer economics/allowance/markets/tax/terms need the existing commercial worksheet; intended payment/storage/alerts/backup recovery needs separate setup and qualification. Do not expand infrastructure to evade these decisions |
| P07 Pilot / release | Offline composed API/browser and named predecessor exhaustive evidence; no live pilot claimed | Representative customer purchase→connections→useful manual plan→progress/recovery and human release gates remain. Historical aggregate success does not qualify current head |

## Selected Package: Billing Status Failure Recovery

`portal.mjs::loadWorkspace` included billing in one mandatory `Promise.all` after
`clearWorkspace` hid every billing control. A billing-only 503/network failure aborted
workspace rendering and hid Check Billing Status, preventing the explicit recovery
route while independent authorized reads were available. This is a concrete customer
flow defect outside pricing, TikTok and v6 dependencies.

Isolate only billing GET network TypeError, 429 and 5xx into a local unavailable state.
Keep independent workspace data visible, hide checkout/management, replace prior billing
status/details, and expose manual retry. No inferred unpaid/paid/unconfigured status,
automatic retries, POST, payment, navigation or entitlement change. Authentication,
scope, stale-session and other API failures continue to propagate. A 403/404 on manual
billing retry clears workspace data; 401 retains full session clearing. Final epoch
checks prevent late outcomes from changing another session/workspace.

This package does not make stale billing evidence grant paid access. The server's
production enforcement, exact offer/invoice requirements, original session fences and
account limits are unchanged. A GET displays local billing state; it does not perform
provider reconciliation or prove purchase. Existing background reconciliation is distinct.

## Decisions And Next Work

No new owner answer is needed for this repair. After it, the next larger independent
planning gap is a bounded Q13 field-observation admission/comparison contract, or the
Q10 typed constrained-creative interpretation contract; neither should be presented
as an already completed provider/quality feature. Preserve semantic and ownership
requirements before implementation rather than add generic infrastructure.

Existing concrete owner packets remain current: nominate an advertising/ecommerce
expert and record six separate usefulness judgments in `inlet-owner-quality-gates-20261011.md`;
provide offer economics, account allowance, markets/seller/tax determination and
customer policy in `inlet-commercial-owner-worksheet.md`. Recommend the documented
single fixed monthly workspace subscription structure, without inventing a price,
tax treatment or approving unsupported policy. Those answers are not activation,
credentials, spending, merge or deployment authorization.

## Implemented Package And Checks

The portal now isolates billing-only TypeError/429/5xx read failures, displays explicit
unavailable state and manual retry, and hides old checkout/management controls. It
checks the captured epoch on both the successful and failed final continuation before
rendering, clearing data or propagating errors. No backend, entitlement, provider or
configuration changes. Independent source review closed the package; backlog review
assessed this prioritization, not every historical package's current-head correctness.

Final frozen packet `billing-status-recovery03`, manifest SHA-256
`2e0f60ec643c50e7420e5bae21633a8a2bd444671fe1632e7e11d66ac0727f6c`, is under
`/workspace/inlet-evidence/20261012/`. Four static checks passed: whole Ruff,
configured mypy (1,558 files), exact six-node collection and `git diff --check`.
Six pytest cases passed with no skips: three shell routes, static asset boundaries,
Node contract suite and actual Chromium DOM journey. The browser covers initial503,
manual recovery,500/429/network failure after actionable status, scoped GET-only
recovery,403/404 denial,401 session clearing, and delayed success/503/401/403/404 from
the old session. Existing goal/save/replay and safe-rendering journey assertions remain.
These use synthetic browser fetch responses; no database, real IdP, Stripe or payment
operation was exercised by this package. No backend tests were rerun because backend
bytes are unchanged. Original exit/log/XML, exact identities and source checks are retained.

Attempt01 passed before review added final continuation guards; attempt02 passed four
static checks but left its six runtime cases unrun after the error-continuation review
finding. These predecessors remain separate; attempt03 alone qualifies final code.
No failed test was ignored and no unchanged retry was used. This package does not
qualify v6, close the historical incident, or establish live purchasability.
