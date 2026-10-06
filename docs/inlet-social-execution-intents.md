# Social Customer Execution Intents

This package connects a customer's confirmed social configuration to durable paused
creation, original-attempt recovery, and separately approved activation. It does not
install a provider runtime, qualify a native spending ceiling, or authorize live work.
The public marketing page is unchanged.

## Customer And Server Interfaces

`POST /api/customer/v1/workspaces/{workspace_id}/execution/social/creation-reviews`
accepts only `configuration_review_id`, `expected_configuration_digest`,
`mandate_id`, and `mandate_revision`. Extra keys are rejected. The saved configuration
must be an owned, confirmed version2 review. Version1 remains historical and cannot
be silently promoted into authority. The server derives account, native generation,
source, option, profile, media pair, declaration and canonical plan.

The read-only `GET .../execution/social/confirmed-configurations?draft_id=...`
returns at most 50 owned confirmed records through the strict historical serializer.
A record appearing here is not proof it is currently executable. Current selection,
original confirmer ownership, original caller session, native qualification and
spending consent are rechecked on each forward action.

`CustomerExecutionRuntime.social_review` is an optional server-owned
`SocialReviewRuntime`. The default customer runtime factory still returns `None`.
The standalone configuration-review dependency and this execution dependency must
be deliberately assembled from the same reviewed profile/rules/catalog ports.
Environment mismatch, changed profile/rules, missing confirmation, expired catalog,
unqualified native discovery in live mode, or any existing coordinator qualification
failure blocks execution. DSA-required profiles and personal declaration inputs remain
unsupported. TikTok native discovery remains an explicit unverified producer gap.

`app.publication.social_execution_intents.refresh_social_execution(db, workspace_id,
review, actor, media, runtime)` refreshes the exact current selection before creation
approval, run admission, forward advancement and activation preparation. Catalog IO
occurs after committing existing locks. The original session callback is retained
and called again after IO before economic locks. A request-local pure validator then
checks the complete configuration and catalog expiry at the coordinator's subsequent
locked boundaries, including after qualification and credential-context IO. Any existing server configuration validator is also preserved. No mutable
adapter state or caller-supplied proof is introduced.

Historical reconciliation deliberately does not require this current-discovery helper:
it reads the original owned request and latest receipt sequence without re-emission.
Absent current discovery must not prevent resolving an earlier uncertain obligation.
The existing exhaustive purpose dispatcher preserves optimization's separate runtime.

## Customer Journey

`/app/execution` retains Google configuration and adds selection of an already
confirmed social configuration after separate period/account spending consent.
Customers see readable budget, creative, targeting, media-pair and attribution settings,
then approve the exact canonical review, create a durable run, and advance individual
reviewed steps. Paused creation is followed by a separate activation review. Existing
owned run URLs recover status and receipts; logout clears them. Contract-test mode
is explicitly labeled as making no provider-account changes. Activation observation
still does not prove delivery time, causal lift, or reservation settlement.

## Offline Qualification

Tests use actual API routes, durable database models/coordinators and concrete Meta
and TikTok HTTP adapters with injected mock HTTP only. Session revocation during
catalog IO and expiry during qualification must deny persistence; changed rules deny
forward approval. Recovery with discovery absent must retain original request identity
and make no new write. Actual HTTPS Chromium journeys cover readable configuration,
separate consent, paused creation, activation, receipt recovery and logout on SQLite
and disposable PostgreSQL. Google and optimization route regressions remain required.

No new migration or retention exception. The existing 0059 strict nonpersonal record
and optional canonical reference are reused unchanged. Root integration owns 0060 and
assembled Full/hosted validation. This package is not a production qualification.
