# Production Billing Assembly

This package binds the existing paid customer paths to production identity without
changing commercial policy. Parent approved the contract before implementation.
Base: PR193 `43b7e38`; predecessor migration formatting matches root `cbfb835`.

## Implemented Boundary

`APP_ENV=production` always routes shared `paid_work` through `live_paid_work`,
regardless of billing mode or the historical optional rollout flag. This covers
advertising source activation, Google selection, post-sync analysis (including
its final persistence recheck), campaign/media review, publication preparation,
and mandate actions. Live execution policies already independently use the strict
live gate at review, claim and final emission. Missing live scope, disabled live
billing, test evidence, unqualified offers and stale/failed qualification cannot
satisfy this gate.

The default production billing factory cannot assemble a test transport. Billing
status with unavailable production transport never falls back to legacy test
rows: it reports no selected scope when no live scope can be established, and
reports enforcement as mandatory. A selected live scope can retain its historical
status while purchase/management remain unavailable. Scope is nullable in this
unconfigured response; portal code does not use scope to authorize actions.

Explicit historical webhook receipt lanes, exports, settlement and original
financial receipts are unchanged. Receiving a signed event does not itself grant
entitlement. Unknown checkout keys and immutable original offer recovery remain
owned by the existing service; no fresh request or offer substitution was added.

## Remaining Code and Readiness

The default transport still requires a valid current configured offer. Historical
management/reconciliation with a removed or syntactically invalid current profile
therefore remains unavailable through that factory even though original bindings
are retained. A separately qualified receipt-only factory would be additional
engineering; do not delete or reinterpret the original binding to recover it.
Current supported fixed licensed offer excludes additional tax/trial/discount,
credit/grace and multi-item behavior; these are engineering gaps if desired.

Before any separately authorized release, the owner must supply the reviewed
merchant identity and supported offer values, choose the allowed commercial
behavior, and configure the dedicated live webhook plus secret references. Use
production environment consistently on web and worker processes, apply migrations
with old writers quiesced, and qualify the same offer and mode across workers.
Keep live enablement off until those checks and the independent deployment gate
are satisfied. No values, credentials, charges or live changes are supplied here.

## Evidence

Baseline `/tmp/inlet-billing-assembly-before.log`: eight failed assertions across
SQLite and PostgreSQL, including four actual `app.main` upload requests returning
200 despite production with disabled/test billing and optional enforcement off.
This was a product reproduction, not a mocked authorization helper.
Final checks are recorded in the delivery PR. Full suite and live verification
remain pending; deterministic provider seams do not qualify a production release.

Final validation: 144 passed in 54.54s across billing assembly, scopes, offers,
customer billing and customer runtime scheduler tests (both configured databases).
Log: `/tmp/inlet-billing-assembly-final.log`. `ruff check .` passed, configured
`mypy` passed all 511 source files, and `git diff --check` passed. The only
migration changes are the root's existing formatting corrections; no schema change.
