# Integrated Inlet Candidate Acceptance

This is the current candidate view for draft PR130. Earlier package matrices are
historical checkpoints, not current completion claims. Main remains `ea3591c`.
No live product, provider, purchase, deployment or advertising-spend qualification
has been performed. Focused tests establish only their described offline behavior.

| Package | Integrated implementation and evidence | Remaining acceptance |
| --- | --- | --- |
| B01 | Positive-conversion diagnostic regression, including 100 clicks / 10 conversions / $100 spend, and true zero-conversion coverage | Preserve through integrated Full and CI |
| B02 | Customer identity, scoped roles, revocable sessions, post-lock/provider revalidation and concurrent authorization tests | Configured identity provider and unrelated live customer qualification |
| B03 | Idempotent workspace provisioning and owner membership; customer signup journey | Live signup and recovery under deployed configuration |
| B04 | Explicit workspace/connection/account ownership, scoped imports/jobs and database constraints | Full integrated isolation suite and unrelated live accounts |
| B05 | Canonical Shopify merchandise sales net discounts/refunds, store-local windows, 13-month retention, erasure suppression and owned measurement APIs | Actual historical publication manifests and privacy epochs underway; deployed source permission/completeness reconciliation |
| B06 | Editable versioned goals, immutable confirmed baselines, scoped creation receipts and browser review/confirmation | Complete connected customer workflow and qualified historical baselines; goal confirmation is not spending authority |
| B07 | Versioned mandate simulation, reservations, cancellation, uncertainty and cumulative-cap guards | Separate production mandate/coordinator implementation underway; qualified exposure bounds; validate draft aggressiveness policy |
| B08 | Concrete Google connection/import runtime, current customer consent/account selection and disconnect UI | Live app permissions, callback, refresh/revocation and historical reconciliation |
| B09 | Reviewed Google optimization planning and concrete adapter work | Production mandate execution, authoritative portfolio exposure and controlled live qualification |
| B10 | Scoped Meta child reporting, current customer OAuth/selection/disconnect UI and stale-grant fencing | Live permissions/account reconciliation and supported optimization matrix |
| B11 | Scoped TikTok lifecycle/import runtime and paused publication adapter | Customer setup UI, production coordinator and live advertiser/reporting qualification |
| B12 | Klaviyo/HubSpot/Omnisend scoped customer-context transport, suppression and quota defenses | Complete customer connection journeys and live data-purpose/permission qualification |
| B13 | Billing provider transport, webhook reconciliation, checkout/return/management UI and entitlement guards | Commercial configuration, actual purchase/cancellation and closure billing policy |
| B14 | Supplied-media review, private media storage adapter, bounded real video decoding and browser preview | Configured storage/provider media qualification; production publication depends on explicit review |
| B15 | Google publication compiler/HTTP adapter, immutable qualification/review, durable offline execution core and cancellation/duplicate-effect regressions | Actual production authority/coordinator, reviewed activation and authoritative settlement; no live enablement |
| B16 | Concrete Meta/TikTok paused publication adapters and shared typed contracts | Complete coordinator-backed campaign journeys, optimization execution and provider capability/exposure proof |
| B17 | Strict comparable-window evaluator and conservative source projection | Published historical manifests, privacy-fenced persistent aggregates, durable production receipt projection and measured feedback |
| B18 | Customer navigation, signup, goals, billing, Google/Shopify/Meta connections, media review and local-closure receipt UI | Remaining source setup journeys, activity/support, complete export/closure; public website is separately owner-managed |
| B19 | CI gates, explicit global model registry, worker authentication, private storage and native restore exercise | Green integrated Full/CI; deployed readiness/alerts, retention and recovery qualification |
| B20 | Offline unrelated-tenant, browser, revocation, retry and scope tests | Unrelated real pilots across every supported launch workflow, purchasing, closure and operations |

## Current Integration Evidence

At candidate `a9d4abb`, the focused PostgreSQL/SQLite/browser/video suite passed
87 tests with seven SQLite-only skips; Node portal tests passed ten; whole mypy
passed 359 files; Ruff and PostgreSQL base→0047→base→0047 passed. Subsequent closure
UI and deterministic browser readiness/target-discovery repairs require the new
combined browser run and frozen Full/CI. Individual package green tests do not
substitute for those runs. Exact failures and follow-up checks live in
`docs/inlet-progress.md`.

## Next Dependency Order

1. Freeze and qualify the assembled candidate, including independent review findings.
2. Finish the separate production mandate/ledger and real-adapter coordinator with
   immutable authority, receipts, activation and settlement; preserve uncertainty.
3. Finish bounded owned export, closure worker draining and explicit disposition.
4. Produce privacy-fenced historical measurement manifests and measured action feedback.
5. Finish remaining customer-source journeys, operational evidence and unrelated pilots.

No percentage aggressiveness setting authorizes a higher overall spending limit.
New campaigns and creative always require customer review. Local closure currently
blocks local work and records unresolved external obligations; it does not assert
that external ads stopped, billing ended, workers drained or historical data was erased.

## Specific Current Critical Path

The assembled candidate is **not purchasable SaaS**. It contains a large offline
implementation, but no complete provider-backed optimization/purchase/pilot journey
has been qualified. Credentials alone would not close the remaining engineering gaps.

1. **Integrated correctness:** obtain terminal Full and hosted results for frozen
   `0cf6706`; incorporate the retained Meta account ownership repair; qualify the
   resulting exact successor artifact. The current local/hosted runs are pending.
2. **Production execution:** connect the concrete Google/Meta/TikTok adapters to
   the separately consented production mandate and shared exposure ledger. Complete
   durable claims, exact review-to-request binding, unknown outcome reconciliation,
   separately reviewed activation, and evidence-based reservation settlement. This
   blocks B15/B16 and the real receipt input for B17. Existing simulation authority
   cannot be upgraded into production authority by configuration.
3. **Measured feedback:** publish actual atomic commerce history with connection
   generation and privacy epochs, then join the owned latest provider receipt to
   comparable observations. Finish advertising-source publication adapters and
   explicitly qualify maturity/effect-time policies. Stored snapshots or a pure
   comparator alone do not satisfy measured optimization.
4. **Complete customer control:** finish remaining TikTok/CRM setup, source-aware
   export invalidation, closure worker draining and external-obligation handling,
   activity/support, and full visible customer workflows. Local closure is not
   provider shutdown, billing cancellation or data erasure.
5. **Operational and commercial qualification:** test final route boundaries,
   readiness/schema compatibility, recovery after erasure/revocation, alerts and
   unrelated offline journeys. Then present concrete price/terms/retention and
   intended-environment decisions, with explicit authorization required before
   provisioning, purchases, provider changes or deployment. Unrelated live pilots
   remain mandatory acceptance evidence.

Parallel implementation follows the agreed production receipt, source-privacy,
and lifecycle/export interfaces. Public website work remains owner-managed.

## Predecessor Check Disposition

| Frozen predecessor | Local Full terminal result | Hosted terminal result | Disposition |
| --- | --- | --- | --- |
| PR112 `f698dea` | Failed:1578 passed,38 skipped,1 nested failure; Shopify initial-session readiness race | Run37410847813 failed:1581 passed,32 skipped,4 failures; FFmpeg decoder cases plus nestedFull | Superseded failed candidate; decoder and deterministic browser repairs incorporated into130 |
| PR118 `216fda2` | Failed:1597 passed,38 skipped,1 nested failure; billing initial-session readiness race | Run37410393272 failed:1597 passed,32 skipped,7 failures; decoder/upload cases, nestedFull and Chromium page-target discovery | Superseded failed candidate; repairs incorporated into130 |
| PR130 `0cf6706` | Running; no terminal success claimed | Run37412515307 running | Frozen coherent candidate; known retained Meta ownership repair remains a separate successor change |

These predecessor runs did not pass. Earlier successful foundation runs remain
historical evidence only and are not substituted for final integrated acceptance.
