# Offline Publication Coordinator Foundation

This package implements shared contracts and a durable coordinator, not B15/B16
provider publication. There is no HTTP publication client, production authority,
customer publication route, worker activation, or live spend authorization here.
The only registered compiler and exact accepted transport are local fixtures;
`get_publication_transport()` returns None. Existing B07 simulation and Google live
mutation boundaries remain unchanged.

## Contracts

`PublicationReviewV2` is a new approval document containing the immutable B14 review,
its digest, server-resolved external advertiser identity and `FixtureReviewFields`.
The latter admits only explicit synthetic tracking, bidding and horizon-exposure
settings. It cannot represent a real provider configuration. Existing B14 offline
approval is necessary source evidence but never sufficient publication approval.

`PublishPlan` binds workspace, advertising account/integration, native connection
version, mandate/revision, review digest, conservative synthetic exposure and a
maximum16-step ordered DAG. A registered server compiler supplies every operation.
Persisted plans are recompiled and compared before use; callers cannot supply an
HTTP method, URL, arbitrary request body, or unregistered operation. This release
compiles a four-resource paused budget→campaign→group→ad fixture graph.

`ResourceRef` names a dependency's typed resource output. `BoundRequest` substitutes
only a verified same-plan/same-scope receipt and binds the exact plan, operation,
parent, attempt fence and dispatch time with a canonical domain-separated digest.
`PublishReceipt` binds scope, plan, step, fence, request digest, observation time and
verified paused resource. Receipts before dispatch or after the verifier's clock are
rejected. Successful receipt resource IDs cannot be overwritten by conflicting
callbacks. Immutable receipt records retain the original bound request and fence
across later retries; stale attempt receipts cannot change a newer attempt.

Ports are `PublicationCompiler.compile(review)`,
`PublicationTransport.apply_once(request, now)` and
`PublicationTransport.reconcile(request, now)`. Future provider configuration and
operation types require explicit strict contract extensions, a registered compiler,
a new exact customer review and qualified authority; a generic HTTP dictionary is
not an extension mechanism.

## Authorization And Accounting

`DatabaseFixtureAuthority` checks current customer owner membership/user status,
workspace, billing entitlement, B14 revision/media integrity, mandate revision and
simulation mode, native generation/status and both native/internal external
advertiser identity. Every next step rechecks the simulation kill switch and the
shared mandate preconditions, including high-water spend and cumulative exposure.
Lock order is workspace→mandate→draft/native connection→publication/action→step.

One B07 simulation action and reservation cover the entire DAG. The new exact
publication approval approves that action; it is not inherited from B14 approval.
B07's durable dispatch commit is followed by lock reacquisition and a fresh step
selection before a step attempt is marked dispatching. This ordering is essential:
the initial concurrency regression reproduced a duplicate claim through that commit
gap and now verifies only one worker receives a dispatch request.

A crash or timeout after the durable step marker produces uncertainty, never an
automatic retry. A verified effect binds its receipt and permits the next step.
Only authoritative fixture no-effect permits a new attempt/fence. Unknown or
conflicting evidence blocks later steps. Lease age is not proof of no effect.
Per-step success or no-effect never releases campaign-wide exposure. Cancellation
before any dispatch may release it through B07; after dispatch cancellation only
freezes progression and retains the shared reservation, even with verified paused
resources or partial no-effect receipts.

`paused_verified` means every fixture resource was read back paused. Activation
requires a separate exact digest of the verified resource graph. This package stores
that offline approval only: it does not execute activation. The reservation remains
held; there is no fabricated zero-spend settlement or general provider cleanup.

## Schema And Checks

Migration0040 descends0039 and adds composite-owned publication plans, step attempt
state and immutable receipts, plus the mandate-action composite candidate key used
by ownership foreign keys. Unrelated legacy CRM and analysis enum autogenerate drift
was removed before running the migration. Disposable PostgreSQL upgrade and
0040→0039→0040 roundtrip are required checks.

Tests cover exact separate review, unregistered compiler rejection, request replay,
one shared reservation, partial DAGs, pre/post-effect timeouts, authoritative
no-effect retry, preserved original request/fence, stale and foreign receipts,
receipt time bounds, current ownership/generation/entitlement/mandate/kill-switch/
high-water changes, cancellation, separate activation approval, fixture-only transport
substitution rejection, and concurrent PostgreSQL claims.

## Remaining Implementation And Qualification

Provider-specific tracking/bidding/budget/targeting/identity schemas and actual
Google/Meta/TikTok compilers, HTTP adapters, qualified idempotency/reconciliation,
production mandate authority, activation and spend settlement are still code work.
Customer routes, background publication dispatch, live grants and pilot verification
remain separate. This foundation is not a purchasable/live publication milestone.

### Dispatch commit and reconciliation boundaries

The mandate dispatch marker commits before the first publication step. Every
subsequent lock reacquisition revalidates current cancellation/approval/action and
mandate authority; authorization before that commit is insufficient. Cancellation
that wins this interval must prevent the first resource request. Reservations remain
conservative until independently justified settlement.

An empty fixture resource dictionary is not proof of no effect: a claimed worker may
not have submitted yet. Reconciliation returns unknown and preserves its original
fence, so a delayed submission cannot coexist with an automatically retried attempt.
No absence-based retry or production idempotency claim is supported.
