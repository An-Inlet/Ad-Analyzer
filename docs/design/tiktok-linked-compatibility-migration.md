# TikTok Linked Creation Compatibility Fixtures

Base: author backend 494ec217, with root UI f7a5667 merged only as a test dependency.
This package changes test fixtures and evidence records only. It adds no production
exemption for contract scenarios or CUSTOMIZED_USER creation.

## Coverage Mapping

| Previous Fixture | Current Meaning |
| --- | --- |
| `test_tiktok_runtime_api` five future custom-identity journeys | Actual old configured route explicitly denies a new review with the fixed policy code and zero new reviews/attempts/holds/provider writes. The five complete/unknown creation/unknown activation/media/confirmation journeys are retained in author-owned `test_tiktok_linked_runtime_api`, using genuine linked configuration and consent. |
| `test_social_coordinator_journeys.ready` TikTok branch | Uses `ready_linked`: current linked plan, durable declaration/consent, actual serializer/readback. Meta remains unchanged. Duplicate, foreign scope, unknown original attempt, revocation/reconnect and held-reservation assertions remain. |
| `test_social_activation_journeys` TikTok branch | Uses linked creation plus actual `LinkedPushTikTokActivationHTTP`, preserving separate approval, exact full graph preflight, original hold, unknown/no replay and authority drift assertions. |
| `test_tiktok_legacy_creation_policy` | Calls explicitly named `ready_legacy` within its pre-existing narrowly scoped pre-policy setup. Production guard is restored before all forward-denial/readback/reconciliation assertions. |
| Pure `test_social_customer_producer` | Retains old canonical compiler contracts using explicitly historical setup. The setup-only policy patch ends before producer assertions or any customer route. These pure contracts do not confer new execution permission. |
| `test_customer_social_execution` old TikTok path | Keeps source/CSRF/foreign scope/tamper checks, then expects the deliberate future-creation denial. Meta positive path remains. New actual configured linked API/browser suites carry future TikTok success and uncertainty coverage. |
| Configured TikTok browser eight scenarios | All complete/unknown/unknown activation/revoked/source/media/declaration/profile parameters remain on SQLite and PostgreSQL. The actual linked UI decodes video/cover, records four declarations, confirms exact configuration, selects separately API-consented mandate, reviews/approves paused creation and creates a run. The ordinary execution page then drives existing state/unknown/activation/receipt/revocation assertions. |

The browser fixture prepares a mandate through ordinary customer endpoints and
explicit consent, never an inserted mandate/review/run/attempt/hold. Root's separate
new linked TLS test covers the complete initial UI path as well. No runtime getter
is overridden in these configured browser journeys. Private identity and provider
HTTP are controlled offline seams; no account API or credentials are used.

The saved-run browser opens the real `/app/execution/{workspace}/{run}` URL. Its
environment assertion reads the saved run's actual Contract Test label, rather
than the workspace capability panel that is not loaded during direct run recovery.

## Failure Evidence And Validation

Initial migrated browser16 cases failed in the new driver because its getElementById
helper was accidentally passed CSS selectors for nested video/image. Replaced that
with actual panel.querySelector calls, preserving playable/decoded assertions.
The first corrected complete case then failed its environment assertion because
saved-run direct navigation intentionally does not load the workspace capability
panel. The exact saved run carries its own Contract Test label; moving the assertion
to that actual label retained the original no-live-claim requirement. Corrected
SQLite complete journey passed in35.11 seconds before the full scenario cohort.
No production code changed to fix either test-driver error.

Core migrated coordinator/activation/legacy rollout/runtime boundary cohort:
74 passed in307.69 seconds, `/tmp/tiktok-linked-compat-first.log`.
Downstream producer and customer social execution:28 passed in69.42 seconds,
`/tmp/tiktok-linked-compat-producers.log`. Whole Ruff and mypy890 passed; Node syntax
and diff checks passed. Every pytest cohort uses `--durations=20`.
Initial failed logs remain `/tmp/tiktok-linked-compat-browser.log` and
`/tmp/tiktok-linked-compat-browser-one.log`; no prior Full pass is asserted for this
successor. Final browser/direct-consumer counts are recorded in the progress ledger.

Direct historical fixture consumers (configuration API/UI, review and populated
migration) also passed:14 tests,57.45 seconds,4 existing migration warnings;
`/tmp/tiktok-linked-compat-legacy-consumers.log`. This verifies their retained
historical semantics after the setup naming/policy boundary change.

Final configured browser cohort:16 passed in412.39 seconds (6m52s), preserving all
eight scenarios on both databases. Slowest case37.62 seconds (PostgreSQL complete);
unknown creation12.45/12.66 seconds. `/tmp/tiktok-linked-compat-browser-final.log`
retains durations20. Total affected terminal suites:132 passed (74+28+14+16).
No Full, remote, live account calls or advertising changes occurred.
