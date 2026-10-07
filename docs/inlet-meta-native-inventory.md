# Meta Native Inventory Diagnostics

`app/collectors/meta_native_inventory.py` implements the additive diagnostic port frozen
in [production spending readiness](design/production-spending-source-readiness.md).
It does not implement PortfolioFacts, original-request closure, settlement, an exposure
profile or a default live factory. No database writes, credentials, cap changes or
provider mutation are performed by this package.

`MetaNativeInventoryHTTP(request, now)` accepts an exact owned ExecutionAccount,
connection generation, mandate binding, currency, timezone and <=366-day requested
period. The caller must resolve current owner/session/mandate authority; the injected
context resolver must freshly check current account generation on every call. Context
is checked before and after each HTTP read and again before result delivery. A resolver
that simply returns stale cached credentials is not a production integration.

The actual HTTP code reads fixed v26 `act_{id}`, `/campaigns` and `/adsets` paths. It
requests all SDK-known effective statuses, including archived/deleted resources.
The exact pinned Campaign enum has six effective statuses; AdSet adds CAMPAIGN_PAUSED.
Other resource types' review statuses are not inferred into those enums. The result
explicitly says `status_scope=sdk_known_effective_statuses_only` and
`all_effective_statuses_complete=false`: a completed query does not establish that
the pinned SDK enumerates every current provider status.
There are at most ten pages per edge, 200 campaigns and 200 ad sets. It uses only opaque
bounded `after` cursors, never a provider next URL. Foreign accounts, missing parents,
duplicate rows, cursor loops, malformed counters, mismatched currency/timezone and
expired/changed context reject the result. Unknown returned statuses mark inventory
incomplete. Absence of a currently visible historical resource cannot prove it had no
liability; `historical_obligations_complete` remains false even after all pages finish.

Transport limits: redirects and environment proxies disabled, 5-second connect and
12-second read/write/pool timeouts, 60-second elapsed checks around blocking reads,
21-request maximum, one MB per response and four MB per collection. Context-resolver
work must itself be bounded by its caller. App-secret proof is optional and request
URL logging is suppressed through the existing private HTTP context. Exceptions emit
fixed codes, not provider messages, tokens, cursors or identifiers.

Native observed counters are named `*_native`, with
`unit_semantics=native_integer_unqualified`. Field types alone do not establish every
counter's currency unit, period epoch, credits/adjustments or accounting basis. Missing
amounts/flags/times remain null; explicit native zero is preserved without implying
unlimited or exhausted delivery. Account amount_spent is not relabelled as requested-
period reported spending. Current cap/budget observations do not bound later writers.

The result schema forces watermark, U/F/P and counter epoch to null, pending-cap and
historical completeness to false, and cap/accounting semantics to unqualified. Its
inventory-read completeness flag describes completed bounded API reads only, not an
atomic native snapshot or complete obligations. No diagnostic-to-proof converter or
production factory is installed.

## Primary Schema References

Pinned official Meta SDK `efd8423a2e595ea8d4c04eb824ce113f2f1d68cd`, inspected 2026-10-06:

- [AdAccount fields and campaign/ad-set edges](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adaccount.py)
- [Campaign fields, status enums and budget flags](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/campaign.py)
- [AdSet fields, status enums and lifetime_spend_cap](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adset.py)

These schemas establish the requested native fields, not their suitability as a strict
spending guarantee. [Remaining source/adapter work and owner choices](design/production-spending-source-readiness.md)
are explicit. No access-only completion claim is made.

## Offline Verification

Actual MockTransport tests cover wire fields, all-status bounded pagination, next-URL
origin attacks, later-page foreign ownership, orphan children, duplicate/cyclic and
oversized results, malformed/absent/zero counters, private errors/logging, generation
change, request mismatch and expiry during blocking work. The typed result rejects
attempts to supply a finite U/F/P or watermark. New and adjacent Google inventory,
Meta catalog and social optimization suites passed 106 tests without skips. No
provider calls, PostgreSQL changes, Full or live qualification were performed.
