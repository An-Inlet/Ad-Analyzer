# Inlet Current Acceptance Matrix

> Historical October6 snapshot. The [October7 acceptance checkpoint](inlet-acceptance-20261007.md)
> supersedes the current-status claims below, including local Full results and
> configured runtime availability. Original criteria and historical evidence remain
> preserved here; newer integration does not inherit older validation results.

**Review snapshot: 2026-10-06 12:56 UTC.** Assembled code head
`1e337f9eff86353d068e46e2b9ed91c9a2bdec95`, tree
`861f1b557d0c3610865694e31f747269baefb31a`, migration `0076`.
The preceding 31a412d snapshot and its exact evidence remain recorded in the ledger.
The original audit criteria remain authoritative. This matrix reports progress, not
a change to those requirements. This is the current acceptance entry point; the linked older matrices retain their
historical evidence. Later changes require a new dated entry, not retroactive credit.

**Inlet is not yet a live-qualified, purchasable SaaS release.** Substantial customer
and advertising code is implemented and exercised offline. This snapshot has no
successful final aggregate validation, installed production execution/planning runtime,
or verified live customer/provider journey. Routine remaining engineering stays
within the authorized backlog; missing runtime code is not an owner-permission gate.

## Scope And Four Separate Evidence Levels

Product **Inlet**, company **An Inlet**, initially serves Shopify ecommerce brands.
Launch advertising scope remains **Google Ads, Meta Ads and TikTok Ads**. Shopify is
the commerce source; **Klaviyo, HubSpot and Omnisend** are the three planned optional
customer-data connections, with offline connector code now present. Customers can
start with supported tools they already use; this is not a requirement to connect all
three ad platforms or all customer-data tools.

The customer journey remains milestone → editable confirmed goal → budget and
aggressiveness → reviewed plan → monitored progress. Existing campaigns may be
optimized only within an approved spending mandate. New campaigns/creative require
customer review; paused creation and activation have separate approvals. Draft
5%/10%/20% aggressiveness inputs are not validated policy or permission to enlarge
the overall spending limit. No alternative reduced release scope is assumed.

- **IMPLEMENTED** means the named code slice exists, not that the whole backlog item
  meets every acceptance criterion. Partial items explicitly retain their gaps.
- **FOCUSED-TESTED** means relevant offline tests have recorded passes. Mock HTTP,
  fixture policy/financial evidence and actual browser/API/database runs are labelled;
  named test inventories are not claims that every suite ran together at this head.
- **AGGREGATE-TESTED** means terminal required Full gates for one exact artifact.
  `A0` below means **no successful current-snapshot Full/hosted aggregate**. Older
  successful artifacts are listed separately and do not qualify this snapshot.
- **LIVE-QUALIFIED** means verified intended-environment behavior with authorized
  real providers/customers. **None** below means no such evidence is claimed.

## B01–B20

| Item | IMPLEMENTED at this snapshot | FOCUSED-TESTED evidence and limits | AGGREGATE-TESTED | LIVE-QUALIFIED | Remaining code / integration, distinct from external qualification |
| --- | --- | --- | --- | --- | --- |
| B01 Conversion diagnostic | Correct positive/zero-conversion distinction | Regression:100 clicks, 10 conversions, $100 spend does not yield spend-without-conversions; genuine zero remains detected. [Foundation ledger](inlet-progress.md) | A0 | None | Preserve the regression in the final assembled artifact; no known open B01 defect. |
| B02 Identity/access/sessions | Customer identity, scoped roles, revocable database sessions, browser sign-in and fresh original-session authorization fences | Two-user/replica, revoked/stale/session-rotation and post-IO races; actual HTTPS customer journeys. [Identity tests](../tests/test_customer_identity.py) | A0 | None | Qualify configured IdP/origin/cookies in deployment; preserve each new customer operation's session fences. |
| B03 Workspace provisioning | Atomic idempotent signup/provisioning and owner membership | Interrupted/repeated provisioning and account isolation; browser signup path. [Customer portal](inlet-customer-portal.md) | A0 | None | Deployed signup/recovery acceptance, not a missing provisioning API. |
| B04 Explicit ownership | Workspace/customer/connection/account-scoped imports/jobs, generation fencing, closure admission and analysis persistence guards | SQLite/PG isolation, selected-before-closure and post-IO races; analysis shared-session deadlock repaired. [Progress ledger](inlet-progress.md) | A0 | None | Preserve these boundaries in new fixed-window acquisition and feedback workers; verify final integrated worker behavior. |
| B05 Shopify measurement | Owned customer connection, net merchandise-sales/refund ledger, store-local periods, bounded history, terminal publications and privacy hooks | OAuth/API/browser fixtures, refund/date/history/erasure and independent acquisition tests; no live historical completeness claim. [Commerce evidence](inlet-commerce-publications.md) | A0 | None | Qualify actual granted history, source reconciliation and privacy delivery; independent completeness and maturity are distinct. |
| B06 Goals/usage | Editable versioned goals, confirmed owned baseline, usage controls, explicit budget/currency binding | Actual create/preview/confirm APIs, idempotent recovery and stale/foreign/currency denial. [Goal tests](../tests/test_customer_goals.py) | A0 | None | Production connected-baseline journey; interpretation remains manual/mock-first, not a deployed model promise. |
| B07 Mandates/safety | Fixed-period consent/ledgers, reservations, current authority checks, uncertain-attempt retention, settlement and atomic repeat replacement | Three-provider contract fixtures, concurrency, cumulative exposure, late ancestor receipts and preserved holds | A0 | None | Compose and qualify server-owned native financial/transition evidence and permitted operating profiles. Do not relax gates or derive authority from aggressiveness. |
| B08 Google connection | Customer OAuth/account selection, scoped grants, refresh/revocation, imports/backfill/corrections, UI | Actual API/browser plus mocked HTTP, pagination, reconnect, delayed corrections, completion/outbox ownership. [Connection tests](../tests/test_google_customer_connections.py) | A0 | None | Configure and qualify real app/grants, account permissions, callbacks and history; runtime read code exists. |
| B09 Google optimization | Concrete read/compile/write/readback adapter, durable optimization/repeat coordinator, customer reviews, candidate/session-automation surfaces | Real adapters against mock HTTP; request/readback, unknown outcome, owned receipt and session races | A0 | None | Production optimization/candidate/session runtimes remain unregistered; native financial sources and policy qualification are not supplied merely by credentials. |
| B10 Meta reporting | Customer connection/UI, campaign/ad-set/ad grains and current creative context, owned completion/current report | Concrete importer and terminal atomic publication; generation/event/privacy/digest/coverage binding, missing versus zero, child reporting and unrelated ownership | A0 | None | Qualify permissions, supported fields/history and representative volume; historical creative attribution and unsupported campaign features are not implied. |
| B11 TikTok connection/reporting | Customer consent/advertiser selection/UI, concrete HTTP, paced scoped imports/history, renewal/revocation and current reports | API/browser/transport/history and isolation fixtures; generic conversion meaning remains labelled | A0 | None | Qualify real advertiser history and conversion/value semantics; generic conversion counts do not become Meta selected-purchase evidence. |
| B12 Customer data | Klaviyo/HubSpot/Omnisend transports, pacing/renewal, guarded OAuth/account selection/disconnect and customer UI | Mocked provider HTTP and actual customer journeys; safe projections and cross-brand throttling tests. [CRM customer UI](inlet-crm-customer-ui.md) | A0 | None | Live permissions/data-purpose and identity-mapping qualification; no approved persistent private gateway or universal retained enrichment implementation is implied. |
| B13 Billing | Scoped Stripe test/live architecture, immutable offer binding/qualification, checkout/return/portal management, webhook reconciliation, strict production entitlements and GET-only historical recovery | Actual API/browser fixtures; unknown checkout, repurchase, offer drift, paid-invoice evidence, production assembly bypass and original receipt recovery. [Commercial worksheet](inlet-commercial-owner-worksheet.md) | A0 | None | Configure an explicit supported offer/merchant/environment and qualify purchase/cancel. Taxes, trials, discounts, grace or other shapes beyond the narrow supported profile need code if selected; do not infer them from keys. |
| B14 Media/review | Versioned exact supplied-media approval, bounded image/MP4 decode, private local/GCS adapters and rendered review | Real decoding, scope, immutable/hash/size/private-bucket contract tests; browser preflight evidence is artifact-specific | A0 | None | Qualify intended private storage/IAM/media lifecycle and provider uploads; no approved creative generation or object-backup qualification follows from SQL restore. |
| B15 Google publication | Concrete durable paused creation, reviewed DAILY and versioned campaign-TOTAL budgets, exact native serialization/readback, separate activation and reconciliation | Actual HTTPS/API/DB/mocked-Google total and daily journeys; schedules, distinct reservation, stale context and lost responses. [Total-budget customer flow](inlet-google-total-budget-ui.md) | A0 | None | Installed execution/catalog/qualification runtime and supported-profile financial/terminal evidence remain absent; partial/unknown accounting cannot be released on assumption. |
| B16 Meta/TikTok actions/publication | Concrete supported optimization, paused creation, separate activation, customer social configuration and supplied media/cover review | Declared-profile adapters/coordinators and actual customer journeys with mock HTTP; final original-confirmer/session/semantic readback guards | A0 | None | Install/qualify narrow server profiles and financial sources. Meta personal DSA-name capture is unsupported; current no-DSA path must reject required/uncertain declarations. Unsupported campaign types are not qualified by one profile's tests. |
| B17 Feedback/planning | Partial: owned commerce/receipt assessments, retractable feedback/candidate/directional contracts; prospective campaign capsules, chronological sensitivity calibration, initial customer budget preview and durable exact-review handoff | Root 57 passed/1 skipped assembled review/lifecycle/API/browser checks, plus earlier 165/4 core, 48 consumer and independent 9-case composition below; actual Meta HTTP fixture→capture→API/browser preview. Reports are reported-efficiency sensitivity, not mature causal or predictive success | A0 | None | Action-associated comparable fixed-window acquisition and explained operational feedback remain code work. Initial preview handoff now works with the actual configured generic runtime; erased/stale provenance blocks approval and dispatch, while historical reconciliation remains available. Named numerical/retention/maturity policy and qualified evidence are absent. [Next package](design/b17-operational-feedback-next-package.md) |
| B18 Customer application/lifecycle | Signup, connection setup, goals, billing, review/execution UI, activity/recovery, diagnostics, bounded exports and local closure reconciliation | Actual HTTPS/SQLite/PG journeys and composed two-brand archive/closure; capsules expire/erase transactionally and archives stop during delivery. [Lifecycle evidence](inlet-initial-planning-lifecycle.md) | A0 | None | Default-unavailable runtime assembly and external obligations still prevent complete self-service production use. Closure does not prove ads stopped, subscription canceled, all data erased or workers physically terminated. Public webpage is separate below. |
| B19 Operations | Readiness/schema/model/route registries, bounded operator attention, native disposable PostgreSQL restore and retention housekeeping | Populated financial/social/performance restore; initial0075 populated migration roundtrip; database/clock/cleanup races | A0 | None | Repair/complete final aggregate checks; extend populated native backup/restore coverage to newly stored domains as needed. Production alert delivery, object/key backups and full environment recovery remain unqualified. [Restore evidence](inlet-performance-restore-evidence.md) |
| B20 Pilot acceptance | Partial composed two-brand service/API/browser scenarios, held accounting through closure, unrelated-brand continuity | [Offline pilot matrix](inlet-offline-pilot-matrix.md) and [archive/closure composition](inlet-archive-closure-acceptance.md) distinguish fixture boundaries from real APIs | A0 | None | Complete the current-artifact offline acceptance composition, then separately authorized unrelated real pilots through purchase, connections, reviewed ads, monitoring and operations. No live pilot completion is claimed. |

## Runtime And Configuration Blockers Verified In Code

These are current assembly/code gaps, not a claim that an owner merely needs to
provide credentials. Defaults remain deliberately unavailable; this review changes none.

| Actual boundary | Current behavior | Work needed |
| --- | --- | --- |
| [Customer execution runtime](../app/publication/customer_runtime.py) | `get_customer_execution_runtime()` returns `None` | Compose concrete creation/activation/catalog/qualification dependencies with reviewed provider eligibility and financial evidence. |
| [Optimization runtime](../app/publication/customer_optimization_contracts.py) and [social configuration runtime](../app/publication/social_review_runtime.py) | Both getters return `None` | Install intended scoped adapters/profiles and their credential resolution only after implementation/qualification; do not substitute fixture evidence. |
| [Candidate service](../app/optimization_candidates/service.py), [selection](../app/optimization_candidates/selection.py), [review bridge](../app/optimization_candidates/review_bridge.py), [session automation](../app/session_automation/runtime.py) | Runtime getters return `None`; no production producers/policies registered | Finish/compose qualified inputs, stable admission and reviewed policies. Existing session machinery alone does not operate customer campaigns. |
| [Initial planning configuration](../app/initial_planning/runtime.py), [customer assembly](../app/api/customer_initial_planning.py) and [contracts](../app/initial_planning/contracts.py) | Configuration `None`; native dependency inherits unavailable optimization runtime; `review_available=False` remains immutable in stored preview bytes; additive readiness/preparation uses the actual generic optimization runtime | Durable, retractable review handoff is implemented and focused-tested. Named production policy/retention and real financial evidence remain unconfigured; a review cannot grant its own spending authority. |
| [Billing factory](../app/billing/contracts.py) and [offers](../app/billing/offers.py) | Production rejects non-live mode; missing/invalid explicit scope/offer returns unavailable | Actual supported offer and merchant configuration, deployment wiring and payment qualification. Receipt-only recovery cannot create a new purchase or grant forward entitlement. |
| [Export authority](../app/lifecycle/exports.py) | Customer export gate remains default-off; requires consistent privacy writers and fresh authority/expiry checks | Qualify a uniform writer deployment; schema migration alone is insufficient during mixed-version writes. Preserve cleanup/retention for disabled capture and closing workspaces. |

Read-only account diagnostics and current campaign facts exist; they do not fill in
financial authority, delivery timing or outcome maturity. Google/TikTok generic
conversion semantics remain distinct from Meta's explicitly selected purchase event.
A typed source port or compiled total-budget request is not an installed, qualified
provider guarantee. No universal protection from arbitrary outside writers is claimed.

## Next Offline Acceptance Work

1. Repair the actual frozen-run failures on isolated successors and obtain terminal
   Full/hosted evidence for the assembled artifact when the remote hold is lifted.
2. Deliver the B17 fixed-window, action-associated feedback and explained preview
   update, while preserving the completed initial-preview review handoff and its forward retraction. Do not describe
   current sensitivity replay as mature action learning.
3. Complete concrete runtime composition and evidence producers for the approved
   operating profiles. A getter returning `None` is unfinished assembly; relaxing
   financial, original-session or privacy checks is not a substitute.
4. Close the current-artifact customer/pilot and populated restore coverage gaps.
   Add intended alert transport/recovery integration as required: current
   [operational observation storage](../app/operations/observations.py) records
   bounded evidence, but does not itself deliver an alert to an operator.

These are actionable engineering packages, not requests for redundant approval.
Owner inputs and intended-environment qualification below remain separate.

## Customer Journey And Separate Public Webpage

The application now contains customer-facing APIs and browser flows; older statements
that these interfaces do not exist are historical. Offline journeys use real sessions,
CSRF, databases and selected concrete adapters with mocked provider HTTP. Some composed
pilot fixtures still seed identity, Shopify baseline or consent through explicit fixture
boundaries; separate successful component journeys are not one unbroken live pilot.

Later owner instructions make the public webpage entirely owner-managed
([recorded policy](automation-policy.md)). Its original code/design, Squarespace Code
Block, real logo/typography/green palette, Title Case headings, graphics, illustrative
demo and FAQ are not evidence that the application is deployed. The original package
was reported unpublished with email early-access links. The ledger records failed local
materialization, not a verified Salesforce→Omnisend source edit or publication. No current
live webpage state was checked here. Public copy should use Omnisend as the planned CRM
example and must not claim unavailable purchasing or live advertising functionality.
This documentation does not reopen delegated website work or publish anything.

## Exact Validation Provenance

| Artifact/evidence | Actual result | What it qualifies |
| --- | --- | --- |
| Current assembled0076 preview-review package | 57 passed, 1 expected SQLite-only concurrency skip, 231.62s; `/tmp/inlet-next-0076-composed.log` | Real Meta mocked-HTTP preview→review→separate customer approval; original-session, concurrent replay, all forward retraction and historical settlement behavior; not Full/live |
| Current Full-failure repair composition | 36 passed, 4 Alembic warnings, 40.75s; `/tmp/inlet-next-full-repairs-final.log` | Actual social browsers, historical schemas and route boundaries; initial wrong-filename invocation collected zero tests and is not evidence |
| Current0076 migration and native restore | Fresh PostgreSQL head→base→head passed; unchanged populated0075 native drill against0076 schema: 37 passed, 97.79s | Actual migration plus owned initial-data restore. The native archive does not yet populate protected0076 provenance; actual0076 graph coverage is in migration/lifecycle tests |
| Current reviewed 31a412d core composition | 165 passed, 4 expected SQLite-only skips; `/tmp/inlet-next-initial-core-lifecycle.log`; independent actual-capture privacy/disconnect/expiry composition9 passed | Named initial planning/performance/privacy/closure behavior, not Full |
| Current customer preview assembly | 48 passed, no skips in 60.19s; `/tmp/inlet-next-initial-consumer-final.log`; Ruff, mypy 658,JS syntax, diff passed | Actual API/HTTPS browser/native fixture/currency/stale-selection suites, not installed production policy |
| Current social regression repair | 41 passed; `/tmp/inlet-next-social-fixture-repair.log` | Repaired social fixtures/coordinator/customer producer/historical migration subset |
| Current0075 migration | Fresh dedicated PostgreSQL head→base→head passed; `/tmp/inlet-next-0075-roundtrip.log` | Migration roundtrip, not provider or operational restore qualification |
| Frozen `dc3c0d5` Full (separate older artifact) | Terminal exit1: 6 failed, 3616 passed, 68 skipped. Failures: nested wrapper, historical migration, four social browsers. Browser fixture clocks crossed mandate expiry; current harness now explicitly verifies expiry rejection. Repairs passed on the current branch | **Not a pass.** Current fixes do not alter or retroactively qualify this frozen run; terminal log /tmp/inlet-dc3-terminal-pytest.log |
| Latest verified historical local Full: `8efe19668d4920df6607ddd60140ab8ab0779049`, tree `11252fdbc785c270b49a1340dff95506d7391405` | Exitfile 0 and terminal log verified locally. Primary 2639 passed, 59 skipped; final gate 38 passed, 6 PowerShell-unavailable skips, 29 deselected; intervening required gates completed | That exact historical local artifact only. Hosted 37427571832 failed on it; no joint local+hosted qualification |

Historical successful Full logs: `/tmp/inlet-oct06-candidate2-full.log` and
`.exitcode`; retained ledger section “Frozen8efe196 LOCAL FULL TERMINAL SUCCESS.”
These local paths are evidence references, not newly rerun tests or durable remote
artifacts. No newer successful aggregate was reported or found. Never sum focused
counts into an aggregate pass or equate a branch head to a hosted merge tree without
verifying checkout/tree identity.

## Remaining Owner And Live Gates

Use the [commercial worksheet](inlet-commercial-owner-worksheet.md) for concrete
seller/market/tax determination, price/currency/period, allowance and customer-policy
inputs. Numeric values remain unset. Unsupported tax/trial/discount/grace shapes
are engineering extensions if selected, not a request to pretend they already work.

Other genuine decisions/qualification include supported mandate/provider assumptions,
validated aggressiveness and measurement policy, data/media disposition and backup
retention, intended operational ownership/alert destinations, and final release/live
pilot approval. They do not suspend independent fixes, tests or missing runtime work.
No permission to merge, deploy, buy, spend or mutate customer ad accounts is inferred.

Remote push/PR/hosted-CI hold remains in effect. The observed pre-run/Forbidden failures
have no confirmed quota cause. A verified GitHub usage/plan limit would trigger the
owner's all-project stop instruction. The separate exact manual dispatch remains paused.
This docs package performs no remote action, code change, new test run or live check.
