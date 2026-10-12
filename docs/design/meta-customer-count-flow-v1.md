# Customer Meta Website Purchase Count Flow V1

Baseline 8c51d92. Preserve Google routes, document versions and Planning's existing
explicit capture handoff. New Meta routes live under `/reporting/meta`; runtime
injection defaults to unavailable, so registering routes creates no live access.

## Shared Service And UI Interface

- An owned available-range review uses current completed imported performance. It
  does not perform or claim a fresh aggregate provider read. A closed customer date
  subset must lie within that completion. The receipt includes a basis digest over
  owned scope, completion/manifest, exact producer and encrypted-grant fingerprint.
- Event options expose only the documented website-purchase action, labelled
  count-only. The option identifier is bound to that basis. It is a supported
  standard action choice, not a discovered pixel/custom event or proof of live
  availability. No automatic selection.
- Explicit confirmation uses the basis digest plus expected selection ID/digest.
  The current source and completion must still match. Selection is persisted only
  after final original-session authorization in the physical write transaction.
- Capture preparation takes a client nonce and returns a server-issued 128-bit
  HMAC capture ID, domain-separated through the existing Meta Vault. Its commitment
  includes the original session digest, workspace/account, reviewed basis/dates and
  selection pair. Capture verifies that ID before replay or IO; the immutable saved
  ID therefore commits the original intent without a new table or document version.
  A changed basis or session produces a different ID, so it cannot reuse an old one.
  Signing-key rotation conservatively refuses old intents; no unsigned fallback.
  Unknown preparation outcomes retry the same nonce; unknown capture outcomes retry
  the exact returned intent. Preparation performs no provider read or stored write.
- Capture intent retains basis digest, expected selection pair, request nonce/ID and
  dates. Server constructs the request from current owned SQL; callers cannot supply
  native account/event/query identity. Same request ID and intent replays the saved
  capture without provider reads; changed intent or foreign IDs refuse.
- All operations require current customer owner/session/workspace/account evidence.
  Reads require paid access and enabled global/Meta sync controls. Invalidation
  remains available without an injected provider runtime. It retracts old captures
  through existing storage; reconfirmation requires a genuinely current import.
- Capture receipt reports returned rows, rows with explicit zero and rows with
  missing selected count. Omitted campaign-days are not zero. No money, ROAS,
  verified attribution, unique-customer or status-completeness claim.

The Reporting account chooser adds Meta. Its range action says Review Available
Range, uses the available-range route and shows source dates/confirmation rather
than claiming an aggregate refresh. Basis/option/capture state is discarded on date,
account, workspace or session changes. Existing epoch/cookie guards reject late
responses, busy state prevents repeated writes, unknown capture outcomes keep the
same request ID for explicit retry. The final capture uses the existing explicit
Reporting-to-Planning hint; it is never silently added to a saved plan.

## Planning Projection

The shared support gate validates the whole capture graph before admitting only
this exact Meta API/event/owner/query/producer/settings profile with supported
count capability and unsupported monetary cells. Adapter and bundle gap checks
agree. Missing-capture behavior for non-Google accounts is preserved. Older
unverified Meta and TikTok profiles remain unsupported; traffic remains unsupported
for Meta. New plan windows retain partial/unavailable coverage and attribution
limitations. Historical pin validation and stored document versions are unchanged.

## Qualification

Actual owned HTTP/API/SQL fixtures on SQLite and PostgreSQL: selection, replay,
changed basis/grant/head, foreign owners/accounts, CSRF, missing/zero, final-guard
rollback, and capture to generated/saved/history/export plan with original typed
provenance retained. Browser controller exercises repeated clicks, lost responses,
stale responses, account/workspace/session switches and count-only copy. Preserve
Google browser/API and legacy document checks. One heavy slot, frozen cases/source,
first-failure stops and no broad suite rerun. Independent source/evidence review.
No live, hosted, remote, deployment, credential or spend operations.
