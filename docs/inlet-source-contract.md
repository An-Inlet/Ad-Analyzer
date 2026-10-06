# Customer Source Connections And TikTok Preparation

B11 adds an offline customer connection lifecycle and TikTok read adapter. Default
runtime transport is unavailable. No live connection, provider approval or production
advertising behavior has been verified. Source interfaces also reserve Klaviyo, HubSpot
and Omnisend names for B12; those names do not mean working integrations.

## Shared Boundary

`SourceTransport.exchange` returns a bounded grant and explicitly accessible accounts.
`read(account, token, start, end, cursor)` returns a curated page. No mutation method
exists. The token vault binds ciphertext to workspace, provider and connection context.
Callbacks bind state to a current customer session, expire after ten minutes, and consume
state before exchange. Owner/admin selection cannot invent an account. Reconnect rotates
the generation and clears partial coverage; disconnect clears the grant and revokes the
owned integration. Neither operation changes advertising at the provider.

Source grants require the separately configured source encryption key. It has no fallback
to another purpose's key. Fixture tokens are synthetic. Callback access logging now
redacts customer Google/source callback queries as well as legacy callbacks. A shared
same-origin CSRF relay preserves Strict cookies, clears the URL and uses a script-hash
CSP. This is a security correction to B08's callback path.

## TikTok Imports And Reporting

The wire adapter constructs fixed token exchange and advertiser-info requests, then
bounded campaign, group, ad and three metric-grain pages through injected offline IO.
Complete windows publish atomically with explicitly owned jobs; partial pages cannot
become authoritative totals. Conflicting rows, repeated cursors, wrong advertisers,
currency mismatches and missing parent inventory fail closed. Campaign totals are
reported separately from child grains. A rolling thirty-day window permits later
corrections; hourly dispatcher eligibility is tenant-explicit and respects reconnect
generations. The existing job-key completion outbox is reused without renaming its
historical Google table identity.

Customer reporting distinguishes missing coverage from zero spend. TikTok conversion
and value evidence is deliberately unavailable to the optimizer until qualified;
placeholder values cannot trigger a false no-conversions diagnosis. Reported windows
must fit the completed coverage interval. Migration0030 adds the two customer-source
tables and refuses downgrade while TikTok advertising accounts would be orphaned from
the older application model. Production downgrade needs an explicit preservation plan.

## Remaining Acceptance And Live Gates

Runtime provider selection remains unavailable. Refresh/revocation classification,
timeouts, runtime SDK/HTTP construction, provider approvals and real unrelated-account
reconciliation are unimplemented or unverified. Failed malformed pages are rejected;
operator error classification and bounded restart affordances remain B19 work. B18
must expose authorization, account selection, reconnect and coverage in customer UI.
Fixtures are never production data. No TikTok mutation adapter exists in this package.

Official design references consulted 2026-10-06: TikTok Business API SDK token exchange,
advertiser-info and integrated-report examples in
[TikTok's SDK](https://github.com/tiktok/tiktok-business-api-sdk).

## Verification

Seventeen focused tests pass across TikTok/source and Google lifecycle regressions,
including PostgreSQL downgrade preservation. Ruff and mypy (231 files) pass. Required
Full validation and hosted CI results are tracked at the exact package head in its PR
and the progress ledger. These are offline checks, not live-provider acceptance.
