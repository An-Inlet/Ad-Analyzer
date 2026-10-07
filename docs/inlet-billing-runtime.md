# Billing Runtime Implementation

Candidate code on `codex/inlet-provider-runtime`, based on PR73, introduces a real
Stripe HTTP transport. It is disabled by default. Explicit `stripe_test` mode,
synthetic/test key configuration and a pinned API version are required; live keys
and live response objects are independently rejected. No provider requests or
credentials were used during implementation.

Implemented: customer creation, hosted subscription checkout, canonical checkout
lookup, current subscription read, bounded HTTP responses/timeouts, sanitized
transport errors, durable timestamped idempotency keys, nullable checkout URL
recovery, and dependency factory selection. HTTP contract tests use MockTransport.
A portal HTTP method exists but is not yet exposed through the service/API.

Unfinished code: owner/CSRF protected billing-management endpoint and portal tests;
recovery workflow for uncertain attempts older than the safe idempotency window;
retired subscription event handling; scheduler/runtime qualification; complete
entitlement coverage and customer application journeys. An old unknown attempt
fails closed rather than being blindly recreated. No pricing policy is invented.

Source references consulted 2026-10-06:
- https://docs.stripe.com/api/checkout/sessions/object
- https://docs.stripe.com/api/customer_portal/sessions/object
- https://docs.stripe.com/api/idempotent_requests

The checkout contract permits a null URL; the service preserves the recovered
session ID before canonical reconciliation. Stripe may prune idempotency keys
when at least 24 hours old. The adapter stops POST replays at 23 hours; this is a
safety limit, not a completed recovery experience.

## Management endpoint candidate

`POST /api/customer/v1/workspaces/{workspace_id}/billing/management` now checks
current owner membership and CSRF, uses only the workspace's stored Stripe customer
and server-selected portal configuration/return URL, and returns a non-cacheable
short-lived portal URL. The adapter validates returned customer and configuration.
No browser-supplied customer/price/portal configuration is accepted. Creating a portal
session does not itself change subscription state; canonical refresh/webhook processing
continues to determine entitlements. Portal feature configuration is still a release
input; this implementation did not provision it or authorize charges.

Validation:36 focused HTTP+billing tests passed (including SQLite/PostgreSQL membership,
CSRF and suspension checks), Ruff/mypy pass. Full and hosted CI pending. Additional
source: https://docs.stripe.com/customer-management/integrate-customer-portal .

Delayed events for a different, now-terminal subscription are now acknowledged only
after canonical provider reads prove customer identity, terminal status and freshness,
and refresh the actual current subscription. No event payload status can replace the
current purchase. Tests cover canceled and incomplete-expired predecessors with current
entitlement preserved. Combined HTTP, billing and review regressions:80 passed on
SQLite/disposable PostgreSQL, no skips. Ruff/mypy and diffcheck pass. Full pending.
