# Inlet B07–B13 Acceptance Audit

Checkpoint 2026-10-06. Every package below is an **offline implementation slice**.
Passing tests do not complete provider, purchasing or launch acceptance. No live account,
provider call, purchase, merge or deployment occurred. The original audit requirements
remain authoritative; a later package number does not close an earlier gap.

## Implementation And Acceptance

| Package | Implemented surfaces | Offline acceptance evidence | Unimplemented code / product requirements | Separately gated live proof |
|---|---|---|---|---|
| B07 | `app/mandates`: versioned fixed-period mandates, immutable actions/reviews, SQL reservations, fenced claims/dispatch, uncertain reconciliation, pause/revoke; customer simulation API | `tests/test_mandates.py`: SQLite/PostgreSQL ownership, revisions, concurrency, cumulative caps, replay, expiry and cancellation; 18 focused tests | Authoritative provider health/state/exposure evidence and production action integration; validate 5/10/20 policy inputs; customer UI | Qualified platform spending semantics and reporting delay, actual approved mandate, authorized observed-state reconciliation |
| B08 | `app/google_connections`: session-bound callback/account selection, encrypted scoped grants, reconnect generations, disconnect, staged windows, 90-day backfill, completion outbox; injected token/SDK wire adapter | `tests/test_google_customer_connections.py`: 9 focused tests for two unrelated tenants, CSRF/state/session/replay, pagination/partial retry, ownership, reconnect/disconnect, backfill and analysis retry | Runtime SDK factory, refresh/rotation, bounded transport timeouts/revocation classification, usable customer connection UI; current-only advancement misses late conversion corrections (follow-up priority) | Approved Google project/client/developer token, registered callback, real manager/leaf permissions, unrelated-account backfill and reconciliation |
| B09 | `app/executors/google_actions.py`: typed Search/non-shared state, derived validate-only previews, budget/status/negative-keyword plans, exact review, concrete fixture execution and read-back | `tests/test_google_action_plans.py` plus B07: 28 focused tests; generation/state mismatch, timeout-after-apply, unknown/no retry, read-back and retained future exposure | **No live action adapter**; authoritative state/exposure bounds, actual SDK operation execution, provider error classification/partial outcomes and reconciliation; UI | Approved eligible campaign matrix, controlled test-account mutation/read-back and mandate-bound spending semantics |
| B10 | Common ad-set/ad metric grains and compound parents; `app/meta/detail.py`, current creative metadata, scoped customer report; disabled optional collection | `tests/test_meta_detail.py`: 25 focused/detail regressions; populated migration, parent constraints, atomic rollback, cursor/conflict cases, scope/revocation and separate totals | Runtime scheduler integration, historic creative attribution, complete campaign-type optimization support; real Meta customer onboarding still needs journey verification | Exact pinned provider fields/permissions, child/campaign reconciliation and representative account volume |
| B11 | `app/sources`, `app/tiktok/wire.py`, customer source API: session-bound consent, encrypted advertiser grants, reconnect, staged campaign/group/ad imports, rolling 30-day report coverage; shared callback log redaction | `tests/test_tiktok_sources.py` plus Google lifecycle: 17 focused tests; unrelated tenants, partial retries, account/currency mismatch, reconnect/expiry, API access/CSRF, wire paging and downgrade preservation | Runtime HTTP factory, token refresh/revocation/timeouts, customer UI; conversion/value qualification, useful optimization and mutation/publication; malformed-page retry classification | TikTok app/advertiser permissions, callback authorization, live imports/reconnect, reporting and conversion-definition reconciliation |
| B12 | `app/customer_context`: fixed profile-read projection for three providers; transient canonical enrichment through explicit fixture mappings; no financial writes | `tests/test_customer_context.py` plus Shopify measurement: 52 tests; preserved sales, scope/generation, missing mappings, privacy suppression, field exclusion and cursor safety | **No complete customer-data connector**: provider OAuth/refresh, verified live mapping, retained enrichment policy, segments/aggregate context, worker/UI integration and end-to-end optional-source journey; response schemas need exact-version qualification | Klaviyo/HubSpot/Omnisend app/grants and unrelated-customer validation; no guessed identities or Omnisend order-history promise |
| B13 | `app/billing`: durable checkout keys, owner/CSRF API, minimal signed fixture inbox, deduplication, canonical-state reconciliation, periodic refresh/backoff; initial import/mandate entitlement guards | 14 focused billing tests; related 47-test connection/mandate run before final two backoff cases; uncertain checkout, concurrent receipts, delayed events, cancellation/staleness, scope and API revocation | **No purchasable flow**: live provider transport, billing-management/cancellation UI/API, replacement subscription reconciliation, complete legacy job/mutation/account-limit coverage, scheduled refresh runtime, closure/export policy; commercial config unset | Approved price/currency/limits/cancellation policy, payment-provider setup, real checkout/webhook/retry/cancellation journey and operational qualification |

## PR And CI Provenance

The workflow uses the default PR merge checkout. Earlier “exact-head CI” wording was
imprecise: local Full runs used branch heads; hosted CI used the merge SHA shown below.
Fetched merge refs and `git rev-parse <ref>^{tree}` confirm each listed merge tree equals
its corresponding head tree at this checkpoint. This is tree equivalence, not identical
commit identity. CI checkout SHAs for completed jobs were read from `git log -1 --format=%H`
in job logs. Pending rows require terminal log verification before being marked passed.

| Package / PR | Head SHA | Base branch | CI checkout merge SHA | Hosted run / result |
|---|---|---|---|---|
| B07 / [66](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/66) | `7e31642fba815263d441d8ca8f884749de5aeec0` | `codex/inlet-b01-conversion-diagnostics` | `823637fc0d7a727e63cd4e0c3261afbc72933446` | 37390420054: 824 passed, zero skips, all gates |
| B08 / [67](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/67) | `aa4dcff6f09724f5011de1d29d813aee362c8ffe` | `codex/inlet-b07-mandates` | `1a1d8c128d00ffa27f516dbae73b3f8e7c975005` | 37391397871: 833 passed, zero skips, all gates |
| B09 / [68](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/68) | `36c01553e734276d4801e9ad58fb997c14402275` | `codex/inlet-b08-google-connection` | `97d4de840bdfdd115dfb79de839b541eae2b5454` | 37391760028: 843 passed, zero skips, all gates |
| B10 / [69](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/69) | `6f12be883f447b219671de9d116f0ab6c3557323` | `codex/inlet-b09-google-actions` | `88ccf7ba9257ba81b1794bcc51b46d1fcb855590` | 37392693269: 851 passed, zero skips, all gates |
| B11 / [70](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/70) | `5900e69b01ed1633758d206e6974b1e1d0b6ce14` | `codex/inlet-b10-meta-detail` | `1ede8d4440e782f67b9130154f58f9c0a9c5b14a` | 37394058700: 860 passed, zero skips, all gates |
| B12 / [71](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/71) | `7495f68390204688fcf082f138480d7555b8fe2a` | `codex/inlet-b11-tiktok` | `5669d91c33b49dbfc970ad50e8504f3d286243ad` | 37394563656: 868 passed, zero skips, all gates |
| B13 / [72](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/72) | `4d1506ac60f4f68556383c709755fc4d3067a0c4` | `codex/inlet-b12-customer-context` | `b2a8a3499bf9f719e932179a5b66fcb9e3c5de49` | 37395462081: 882 passed, zero skips, all gates |

B12 local Full completed at its listed head: 862 passed, six PowerShell-only skips,
migration round-trip, Ruff/mypy and all required security/privacy/isolation gates passed.
B13 local Full completed at its listed head: 876 passed, six PowerShell-only skips and all required gates passed. Hosted B12/B13 checkout SHAs are now verified against job logs. These baseline checks do not close subsequently reproduced review defects; see `inlet-review-repairs.md`.

## Next Implementation Priorities

1. Finish existing validation runs and incorporate independent review findings.
2. Repair Google late-correction ingestion and test comparable-window freshness; extend
   actual B08/B11 connector lifecycle code rather than treating live proof as the only gap.
3. Complete billing-management behavior and functional onboarding/purchase fixtures;
   preserve unset commercial configuration and unavailable live calls until release.
4. Build B14 versioned supplied-media review and dependent publication, then assemble the
   customer application and coordinated operational gates. Carry every partial above
   into end-to-end fixtures and the release checklist; no checkbox completion by PR count.
