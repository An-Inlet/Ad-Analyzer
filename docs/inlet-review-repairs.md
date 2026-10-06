# Independent Review Repair Checklist

All findings remain associated with their reviewed heads below. Candidate repairs on
`codex/inlet-acceptance-followups` are not merged or live verified. No new package expansion
until these safety/retry regressions are repaired and checked.

| Finding | Reviewed head | Status and evidence |
|---|---|---|
| Rejected claim rolls back validated spend high-water mark | B07 `7e31642` | Candidate repair durably commits validated observation before rejection, without allocating a claim/fence/reservation. Real API request/session-close regressions cover observed50 and observed110 under cap100, followed by lower10. |
| OAuth callback secrets in access logs | B08 `aa4dcff` | Customer Google/source callback filtering already added in B11 `5900e69`. Added actual `uvicorn.access` handler capture for Google, TikTok, Klaviyo, Meta and Shopify; ordinary health request remains logged. |
| Generic draft kind/accounting does not bind executable Google payload | B09 `36c0155` | Candidate binds operation kind, exposure, resource keys, customer/campaign/budget identity and derived positive change before claim/provider application. Persisted generic draft regressions reject mislabeled kind, exposure, resource and accounting. |
| Stale executor session can overwrite a prior reservation | B09 `36c0155` | Candidate refreshes/locks mandate/action before initial connection lock and claim; claim entry also refreshes policy/accounting. Two-session, distinct-campaign regression keeps60 reserved, one action, one side effect. |
| Google documented SDK pages exceed local1000-row cap | B08 `aa4dcff` | Candidate allows documented10000-row pages while keeping total-window50000 bound. Mock SDK tests1001/10000 first-page rows, cursor continuation and identical retries without losses/duplicates. |
| Rejected TikTok pages starve eligible tenants | B11 `5900e69` | Candidate persists sanitized rejection/backoff after rollback, checks generation/status, clears invalid staging and preserves last-success freshness. Batch1 and default20 regressions allow the next healthy tenant to finish. Cyclic cursor and failed publication rollback cases also pass. |
| List suppression treated as global unsubscribe | B12 `7495f68` | Candidate keeps consent separate from global/list suppression scope, excludes list identifiers. Regression proves SUBSCRIBED plus one list suppression remains subscribed with list-scoped restriction. |
| Unknown/expired checkout is stuck; elapsed expiry can create another purchase before completion reconciles | B13 `4d1506a` | Candidate canonical session lookup retains recovered IDs, retires keys only after verified expiration without subscription, and adopts completed sessions instead of issuing another purchase. Timeout, lookup-unavailable and delayed-webhook regressions pass. |
| Canceled-subscription repurchase cannot adopt replacement | B13 `4d1506a` | Candidate verifies current old terminal state and owned completed-checkout lineage before adopting a replacement; fixture cancellation/repurchase/entitlement journey passes. |

Reproduction: new review regressions against untouched aggregate head `4d1506a` in
`/workspace/inlet-review-repro` produced19 failures and3 passes. The same regressions
plus mandate/Google action coverage on the candidate repair produced50 passes.
Logs: `/tmp/inlet-review-before.log`, `/tmp/inlet-review-fixed.log`. Full/CI is still
required before calling the repair package verified. Combined reviewed regression suites now pass101 tests; Ruff and mypy246 files pass. New Full/CI checks are pending.

The separate `inlet-acceptance-matrix.md` traces missing runtime adapters, customer-data
lifecycle, billing management, detailed Meta reporting, portal and operational code.
These are implementation work, not merely credential gates. Safe recovery after provider idempotency-key retention expires, retired-subscription event handling, actual provider HTTP/SDK adapters and runtime wiring remain follow-up code requirements; the current checkout transport is still unavailable by default. Real provider adapter code
and runtime wiring must be completed with injected HTTP/SDK tests and disabled defaults;
actual provider access, advertising changes, purchases and deployment remain unauthorized.
