# Customer TikTok Discovery API

This package adds ordinary configured read-only customer API acceptance to the
reviewed parser and owned collector. It does not upgrade the old social catalog,
CUSTOMIZED_USER publication serializer, linked publisher or live eligibility.

## Frozen Customer Interface

`POST /api/customer/v1/workspaces/{workspace_id}/execution/tiktok/discovery`
requires the original authenticated owner session, matching origin and CSRF header.
Body (`TikTokDiscoveryIntentV1`) contains **only** local `account_id` and explicit
`identity_type`. Unknown fields, browser provider IDs and proof objects are rejected.
The existing owned optimization account-list route supplies local account choices.

Response `TikTokDiscoveryViewV1` is defined in
`app/collectors/tiktok_customer_discovery_contracts.py` (initial freeze2052a5b,
consistency successor e3887f6). It includes:

- observed/unavailable status, fixed reason and contract-test environment;
- full requested-scope identity/pixel counts; event count is null if any pixel's
  events are missing/null, rather than presenting zero as known;
- at most20 identities,20 pixels and20 events per displayed pixel, with separate
  per-list and overall display-truncated flags;
- safe display labels, fixed status/permission states and fixed uncertainty reasons;
- response observation timestamps, `publication_eligibility=not_assessed` and
  `spending_authority=none`.

No native IDs, tokens, credential/session digests, proof documents or raw provider
messages appear. Labels remove control characters and are bounded; consumers render
text, never HTML. Complete traversal applies only to the requested advertiser/type
scope, not all advertiser assets, eligibility, freshness or publication permission.

BC_AUTH_TT returns `business_center_selection_unavailable` after owned access checks,
without any provider call. No owned server BC selection source exists yet; the body
cannot accept a guessed BC ID. Missing configured source returns
`discovery_not_available`, with null counts and no observations. Existing default
source registry remains empty and live admission remains disabled.

## Runtime And Authority

`app.production_runtime.tiktok_discovery.read_configured_discovery` reuses actual
pinned TikTok configuration/source admission, the existing transport seam and owned
vault contexts. It does not invoke financial source builders, credential getters
supplied by customers or execution proof evaluation. Only MockTransport contract-test
sources are admitted; default configuration does not activate this operation.

The API binds its original session/identity authorizer **before** rolling back the
request transaction. That same bound callback flows into every private owned context;
no principal is inferred or rebound from refreshed ORM rows after the rollback.
There are no DB locks held across native reads. Each identity/pixel traversal owns a
fresh transport and closes it. Original token and bounded lifetime also remain fixed
across both traversals. Final projection, source/session/configuration checks and
owned account comparison happen before delivery; any failure discards all results.

## Acceptance And Remaining Work

Final cohort: **41 passed**, zero skips,50.35seconds (22 actual configured API cases
on SQLite/PostgreSQL,10 strict response tests,9 assembled route-boundary cases).
Whole Ruff and configured mypy848 passed. Tests use the normal source registry,
pinned settings, encrypted grants and HTTP MockTransport, without runtime getter
or service-result overrides. No execution reviews, attempts, receipts or reservations
are created; mutation counters stay zero. Coverage includes missing configuration,
missing source, BC unavailable, counts/truncation/null events, CSRF/foreign owner,
revocation/generation drift during IO, final projection revocation and token rotation
between traversals with no partial delivery.

Reusable actual fixture:
`tests.tiktok_discovery_fixture.configured_discovery_customer(engine, configuration,
path, monkeypatch, replicas, video)` returns
`alice, base, intent, requests, control, server`. The underlying fixture uses normal
`configured-tiktok` login; another browser-issued original session for that identity
works without API/runtime overrides. Controls support actual transport callbacks,
missing events and bounded item counts.

An initial test-only privacy assertion matched the word `scope` inside the legitimate
`complete_requested_scope` literal. It was corrected to detect the exact forbidden
JSON key, not loosen the response; subsequent20-case and final41-case cohorts passed.
The UI/browser consumer is a separate dependent package; this API freeze makes no
claim about its pending actual TLS acceptance. No Full, remote calls, live provider
requests, schema changes or financial authority were introduced.
