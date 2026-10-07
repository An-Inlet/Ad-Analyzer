# Owned TikTok Discovery Collector — Proposed Interface

Base parser: `1b5cee8459e7de27c4dcdb23221dfb50877195ec`. Pure parser review found
no remaining actionable findings. This is the next proposed package, not implemented.

## Concrete Composition

A server constructs `TikTokOwnedDiscovery(scope: ExecutionAccount,
contexts: OwnedTikTokContexts, transport: httpx.MockTransport,
clock: Callable[[], datetime])`. It exposes:

- `identities(identity_type: IdentityType, *, identity_authorized_bc_id: str | None = None) -> TikTokIdentityDiscoveryV1`
- `pixels() -> TikTokPixelDiscoveryV1`

The context already binds the actual original actor/session authorizer, separate
session factory, explicit configuration, manifest and owned vault. No browser token,
provider ID, actor callback, manifest or context can construct this service. Scope
must be TikTok and match context environment. The existing `ensure_current()`
contract-test/live rejection remains. Require explicit `httpx.MockTransport` for
this contract-test package, so a configured scenario cannot issue real requests.
This restriction is not a claim that native account eligibility is implemented.

Requests use the exact `scope.external_advertiser_id`. Identities require an explicit
one-of-four type; BC_AUTH_TT requires an explicitly supplied exact BC ID. No automatic
BC inference, linking or fallback. The aggregate describes only the requested type
and BC scope, never every account identity. Pixel discovery uses unfiltered pixels
and explicit ordering, no catalog-only filter that hides inventory. The parser's
request types remain unchanged.

## Owned Authorization Across IO

Before each GET call `contexts.credentials(scope)`, which checks original session,
paid-work entitlement, current source/account generation, owned encrypted grant,
known credential expiry and pinned configuration under workspace-first locks. Its
private transaction closes before HTTP. After every response and at final delivery,
repeat credentials and compare the original token and expiry-bound context plus
exact owned account/generation. Changed/revoked/expired authorization discards the
result. No network operation holds DB locks. Sample fresh UTC after every wait;
monotonic time bounds the whole operation independently of wall-clock changes.

No new secret reader and no fake spending mandate: discovery is read-only. Existing
OwnedTikTokContexts contract-test restrictions remain. Exceptions never include
headers, tokens, provider bodies or names.

## HTTP And Bounds

Only GET `https://business-api.tiktok.com/open_api/v1.3/identity/get/` and
`.../pixel/list/` are callable. Use Access-Token privately, exact documented query
keys and nested filtering serialization. No response advertiser field is invented:
authoritative binding is the owned credential and exact outgoing advertiser query.
If a response supplies an advertiser field, a conflicting value is rejected rather
than used to repair request scope.

Reuse `TikTokHTTPRead` safety conventions: no redirects, `trust_env=False`, streaming
byte cap, sanitized authorization/transient/provider-rejected errors. The current
shared HTTP adapter has no discovery paths and a 30-second individual timeout;
avoid broadening it or changing existing collector semantics. A small dedicated
GET-only transport applies a timeout clipped to remaining total duration.

Proposed fixed engineering bounds: ten pages, two million decoded bytes per page,
eight million total decoded bytes, thirty seconds total, connect timeout at most
five seconds and per-operation timeouts clipped to remaining duration. No retry.
Stop before the next request if a deadline or credential lifetime cannot support it.
These are resource limits, not advertising policy. Oversize, missing, malformed,
rate-limited or interrupted reads return unavailable, not partial-complete inventory.

## Immutable Aggregate Result

`TikTokIdentityDiscoveryV1` and `TikTokPixelDiscoveryV1` contain:

- exact owned `ExecutionAccount` and explicit requested identity/BC scope where relevant;
- tuple of existing strict PageV1 observations and observation start/end timestamps;
- `traversal_completeness='complete_requested_scope'` only after successful full traversal;
- `publication_eligibility='not_assessed'`, `spending_authority='none'`;
- pixel result `scalar_shape_qualification='unverified'` unchanged.

No persisted snapshot or schema is introduced. Per-page `pagination_consistency`
remains unverified because those are original parser observations; the aggregate
separately attests the bounded cross-page checks. Validate identical reported totals
and page size across every page, page numbers contiguous from one, expected final
page from total count, exact page cardinality and total unique count. Zero-result
empty first page accepts documented zero/one terminal-page representations only;
otherwise ambiguity fails closed. Do not synthesize missing pages.

Identity IDs must be present and globally unique; returned identity types must match
the requested type for aggregate completeness. Pixel IDs must be present and unique
as exact `(scalar type, value)` pairs. String `42` and integer `42` remain different
unverified observations, never normalized. Scalar-shape uncertainty therefore still
blocks downstream publication even if traversal is complete. Unknown ownership,
status, deprecated-event flags and missing/null events remain observations; they do
not disqualify traversal or become eligibility.

## Acceptance And Later Customer Consumer

Actual MockTransport tests inspect every GET query/BC filter/header privately and
prove no mutations, retries or real transport. Cover multi-page/empty traversal,
changed totals, duplicates, missing IDs, truncation, excessive bytes/duration,
non-success/redirect/auth responses, revocation/source generation/profile/expiry
changes during a request and final authorization; verify all sessions and HTTP
resources close. Use actual owned vault/source rows and original session guards,
not a bypass callback. Existing TikTok native/publication tests remain unchanged.

No API/browser claim follows from this collector. The next separately reviewed
customer discovery consumer must use local account IDs, original-session CSRF,
owned lookup, bounded readable observations and explicit uncertainty. It cannot
send discovery results into the existing CUSTOMIZED_USER publisher. Linked identity
publication contracts are separately owned and reviewed. No live eligibility or
financial gate is changed by this proposal.
