# Integrated Inlet Candidate Acceptance

This is the current implementation view of `codex/inlet-mvp-next`; draft PR130 is
an older frozen predecessor. Main remains `ea3591c`. Nothing has been merged,
deployed, purchased or qualified against live provider accounts. An offline test
pass is not evidence of a purchasable service or complete live acceptance.

| Package | Implemented and tested offline | Remaining acceptance |
| --- | --- | --- |
| B01 | Positive conversions (100 clicks, 10 conversions, $100 spend) do not produce no-conversions finding; true zero preserved | Preserve through final assembled Full/CI |
| B02 | Identity, scoped roles, revocable sessions, authorization race coverage | New execution facade needs fresh session guards after internal commits/IO; intended IdP/live qualification |
| B03 | Idempotent provisioning, owner membership, customer signup | Deployed signup/recovery |
| B04 | Owned imports/jobs, connection generations, workspace-first closure locks; scheduler self-deadlock repaired | Final assembled isolation and unrelated live accounts |
| B05 | Net Shopify merchandise sales, local windows, refunds, 13-month retention, terminal publications and privacy invalidation | Deployed historical coverage/completeness reconciliation |
| B06 | Editable goals, versioned confirmation and immutable baseline reviews | Complete customer execution bridge and qualified connected baseline |
| B07 | Simulation plus separate production consent/ledger; exact review, held exposure, activation and settlement | Account-set/currency accounting repair being qualified; actual native exposure sources; draft aggressiveness validation |
| B08 | Google connection, import, refresh/disconnect and customer UI | Live permissions, callbacks and history reconciliation |
| B09 | Google optimization adapter ready in PR157; shared optimization coordinator in progress | Integration, complete native portfolio qualification and actual customer/scheduler entrypoints |
| B10 | Meta reporting, customer connection UI, retained-account ownership and concrete adapters | Final optimization integration and live supported-profile qualification |
| B11 | TikTok import/connection UI, actual creation and activation adapters/journeys | Final optimization integration and live advertiser/history qualification |
| B12 | Klaviyo, HubSpot, Omnisend transport, pacing, guarded customer OAuth/selection/disconnect | Live permissions/data-purpose qualification; no persistent gateway enrichment implied |
| B13 | Checkout/return/management, webhook reconciliation and entitlements | Commercial configuration, live purchase/cancel, external closure policy; original hosted billing failure cause unresolved |
| B14 | Exact supplied-media review, private storage and bounded real decode | Hosted browser launch/codec qualification and intended storage/provider media setup |
| B15 | Actual Google durable paused creation, distinct activation and authoritative settlement protocol | Customer intent facade/catalog underway; concrete native exposure/terminal-reporting sources; live qualification |
| B16 | Actual Meta/TikTok durable creation/activation with original-attempt reconciliation | Customer social configuration producer/facade, final optimization integration, provider capability proof |
| B17 | Owned terminal commerce history, privacy-cascading receipt-linked assessment and Measurement History | Current assessments remain insufficient; qualified maturity/effective-time facts and actual comparable feedback are not complete |
| B18 | Signup, source connections, goals, billing, media, activity, recovery and local closure reconciliation | Creation/activation customer API/UI missing and now underway; strict export integration/default gate; external closure/disposition |
| B19 | Readiness/schema checks, route/model registry, operator attention, native restore drill | Green final Full/CI, intended-environment alerts/recovery/retention |
| B20 | Cross-provider service/browser/isolation suites; two-brand composed fixture ready in PR158 | Integrate complete offline pilot matrix; unrelated live pilots and end-to-end purchasing/operations |

## Current Critical Path

1. Finish the demonstrated accounting repairs and strict owned execution/outcome
   serializers, then integrate closure and social journey evidence into one artifact.
2. Finish durable optimization with actual Google/Meta/TikTok adapters and shared
   fresh session authorization. Add the customer intent facade and named provider
   configuration catalog; direct service tests do not replace self-service flows.
3. Supply actual qualified portfolio/native-cap/reporting and terminal-request
   facts. Current server ports and contract scenarios are not concrete live sources.
   Preserve the strict spending ceiling; no daily-budget or reporting-SLO shortcut.
4. Supply qualified measurement maturity/effective-time evidence before claiming
   action comparisons. Current persisted assessments honestly remain insufficient.
5. Freeze the assembled candidate; run Full and normal authorized PR CI, resolve
   actual failures, and complete the explicit offline pilot matrix. Then present
   concrete configuration/commercial/release and unrelated live-pilot gates.

No aggressiveness percentage increases the overall spending mandate. New campaign
creation and activation require their separate exact approvals. Local closure
reports admission fencing and observed local records; physical worker termination,
external ad shutdown, billing cancellation and data disposition are separate.
Export is disabled by default pending uniform writer/deployment qualification.
The public webpage remains separately owner-managed.

## GitHub Diagnostic Boundary

The exact shell workflow dispatch remains paused. Read-only diagnosis found the
execution environment proxy rejects the HTTPS tunnel to `api.github.com` with
`403 Forbidden` before GitHub responds. Connected GitHub Actions reads and ordinary
authorized pushes/PR creation succeed. No plan quota exhaustion is established;
no credentials, network settings or restrictions were bypassed. A verified actual
plan/usage limit still triggers the owner's all-project stop instruction.

## Verification Discipline

Exact commands, results and logs are in `docs/inlet-progress.md`. No final Full or
hosted success is claimed for this evolving successor. Individual focused passes
must not be added together as if they were one full suite. Current owned exports,
new session callbacks and optimization require combined verification before freeze.

## Predecessor Check Disposition

| Frozen predecessor | Local Full terminal result | Hosted terminal result | Disposition |
| --- | --- | --- | --- |
| PR112 `f698dea` | Failed:1578 passed,38 skipped,1 nested failure; Shopify initial-session readiness race | Run37410847813 failed:1581 passed,32 skipped,4 failures; FFmpeg decoder cases plus nestedFull | Superseded failed candidate; decoder and deterministic browser repairs incorporated into130 |
| PR118 `216fda2` | Failed:1597 passed,38 skipped,1 nested failure; billing initial-session readiness race | Run37410393272 failed:1597 passed,32 skipped,7 failures; decoder/upload cases, nestedFull and Chromium page-target discovery | Superseded failed candidate; repairs incorporated into130 |
| PR130 `0cf6706` | Passed (exit0):1813 passed,46 skipped in initial suite; all subsequent gates including final nested Full passed | Run37412515307 failed:1816 passed,40 skipped,3 failures; browser playback and nested validation | Frozen predecessor; successor includes retained Meta ownership repair, commerce publications, bounded export, coordinator/social creation, operator attention and codec-qualified browser repair |

No predecessor has both successful local and hosted final qualification. Earlier successful foundation runs remain
historical evidence only and are not substituted for final integrated acceptance.

## Successor Focused Evidence

At `915fbcc`, the combined exports, TikTok browser, route/model registry, provider attention, social coordinator and diagnostic suite passed **127 tests with one SQLite-only lock-contention skip**. Whole mypy (402 files) and Ruff passed. PR146 playback repair was integrated at `28089c7`; the actual customer portal, campaign review and billing browser suite completed successfully (16 tests). These checks do not establish a successful Full or hosted CI for the successor. No live qualification occurred.

Frozen PR130 local Full completed with exit0; final account-isolation/automation gate passed38 tests with6 PowerShell-unavailable skips. Exact log:/tmp/inlet-mvp-candidate-full.log. Hosted PR146 preflight run37415266510 failed before dependency/test execution: both Google Chrome154.0.8037.57 and Chromium154.0.8037.0 returned browser_no_result. This is not a quota failure. Launch diagnostics/repair remain in progress; local codec success is not hosted success.
