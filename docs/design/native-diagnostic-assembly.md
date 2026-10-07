# Native Diagnostic Ports And Server Assembly

Frozen proposal, 2026-10-06, from `c360555` (PR182). No qualified financial source or
mutation factory is implied. Existing Google/Meta diagnostic interfaces stay compatible.

## TikTok Collector Port

`TikTokNativeInventoryRequest` mirrors the existing diagnostic request shape: exact
TikTok `ExecutionAccount`/generation and `ProviderMandateBinding`, currency/timezone,
positive <=366-day period. `TikTokNativeInventoryContext` extends OptimizationContext
with exact request digest. A fresh resolver is called before/after every blocking HTTP
read; scope/generation/digest/expiry mismatches fail without publishing observations.

`TikTokNativeInventoryHTTP(request, now)` returns the same request, observation interval,
expiry, advertiser status, <=200 campaigns and <=200 ad groups with exact advertiser/
parent identity, observed operation/secondary status, optional native decimal budget,
budget mode and optional declared optimization/schedule fields. Fixed v1.3 advertiser
info/campaign/adgroup GET routes only, STATUS_ALL, numbered bounded pages and stable
pagination metadata. No campaign-ID filtering: collect the accessible whole-account
regular endpoint inventory. No account balance or Budget Manager endpoint is guessed.

Result: `regular_inventory_read_complete` distinguishes bounded page completion from
coverage of every campaign family. `all_campaign_families_complete=false`, historical
obligation/pending-cap/reset completeness false, accounting/unit semantics unqualified,
watermark/U/F/P/account-cap/reset-epoch/terminality null. Smart Plus/GMV Max have separate
SDK endpoints; the regular list cannot prove their absence or historical liability.
Optional omitted values remain null; no default zero/false. Budgets retain exact decimal
observations, not asserted monetary envelopes. No factory, DB writes or financial proof.

## Server-Owned Assembly Interface (Before Implementation)

`NativeDiagnosticService.read(authorized_request, now)` resolves an exact consented
mandate/account selection from persisted workspace-owned policy, not arbitrary browser
native IDs. Constructor dependencies:

- `session_factory`: creates independent short-lived sessions; no caller transaction
  is committed/released by the service.
- `authorize(db, workspace_id, actor)`: server-bound current owner/session authorizer,
  called on each fresh authorization pass, never provided in a browser request.
- `credential_resolver`: provider-aware server implementation reading current owned
  encrypted grants; any necessary Google refresh uses the existing mocked injectable
  OAuth transport outside database locks. No secret appears in request/result/cache.
- Explicit provider HTTP transports and clock, defaults disabled/no singleton factory.

The request carries workspace, server-authenticated actor, exact mandate binding and
selected canonical account ID. The service loads the mandate with existing checks,
selects only its account, verifies native connection identity/generation/currency/
timezone and builds the provider-specific request. It releases its own read session
before external work. Every context callback opens a fresh session, checks authorization
and the full frozen scope again, resolves credentials without holding DB locks, then
rechecks scope/session/consent after credential IO before returning an exact-bound
context. After collector completion, do the same authorization check and compare exact
request and freshness before returning typed diagnostics.

No persistence/cache in the first assembly package: cached evidence invalidation is
separate engineering. No automatic target discovery, claim or provider mutation;
no connection creation, vault-key provisioning, runtime enablement or live calls.
Actual assembly tests must use existing SQLite/PG owned connection records and vaults,
injected MockTransport for refresh/collector traffic, plus role/session revocation,
generation rotation and foreign account during blocking IO. A test-only credential
lambda alone does not close the production credential mapping gap. If the current
provider library lacks a safe read-only token-context operation, add an explicitly
scoped internal helper rather than call a write endpoint or invent refresh semantics.

Root approved this interface before assembly edits. Financial qualification, source semantic profiles, preventive writer
mechanism and terminal-request proof remain absent as recorded in the
[readiness matrix](production-spending-source-readiness.md).

## Implemented Assembly (Offline Verification)

`app/collectors/native_diagnostics.py` now implements the approved port. Construction
requires an independent SQLAlchemy session factory, a server-bound current authorizer,
explicit provider HTTP transports and a clock. There is deliberately no application
factory, route or scheduled activation. Customer assembly should supply the existing
`customer_authority.bind_authority` closure; the request actor alone is not authentication.
The service selects a canonical account only from the exact persisted consented policy,
checks paid/current-goal/account/integration/native generation, and requires persisted
account currency/timezone to agree. Each short private session closes without commit
before OAuth or advertising HTTP; no caller transaction is accepted or committed.

Current encrypted Google refresh grants, Meta bundles and TikTok source bundles are
opened with their actual provider vaults and workspace/connection bindings. Google uses
an additive internal `GoogleHTTPRead.access_context` helper, with actual documented
`expires_in`, fixed OAuth endpoint and existing sanitized bounded HTTP. Its access token
is retained only within one diagnostic call and only while the same current refresh
material remains valid. Every context callback still rechecks current authority and
vault material. There is no persistent token cache or credential write. The helper
follows Google's [refresh/access-token protocol](https://developers.google.com/identity/protocols/oauth2/web-server#offline).
Missing, malformed, expired or wrong-context credentials fail closed. Meta preserves
the existing five-minute remaining-lifetime requirement. A TikTok grant without a
provider expiry receives only a five-minute **local context validity** limit; this is
not an assertion about its native token lifetime or renewal contract.

All three actual HTTP collectors now re-resolve context before and after blocking reads;
Google previously validated a cached context between pages. OAuth refresh gets an
additional exact authorization/generation check after its HTTP response. Final return
rechecks the persisted request, current session/owner and observation expiry. Revocation
cannot undo an already-issued read, but it prevents further reads and release of a
completed diagnostic after the guard observes the change.

`tests/test_native_diagnostic_assembly.py` uses actual SQLite/PostgreSQL records, encrypted
vaults, the customer-session authority closure and MockTransport provider/OAuth responses.
It covers session/role changes, connection identity/generation changes during IO, expired
and cross-workspace vault material, stale mandate/foreign selection and unavailable
transports. This is offline implementation evidence, not live provider qualification.

The result remains the collectors' original typed diagnostic union. U/F/P and reporting
watermarks remain null; no qualified `PortfolioFacts`, native prevention, request finality,
financial settlement, automatic target discovery or optimizer authority is produced.
Operator/customer diagnostic presentation and explicit deployment assembly remain further
engineering; approved provider access alone does not create a spending proof source.
