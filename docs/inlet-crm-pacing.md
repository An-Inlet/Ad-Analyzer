# Paced CRM Page Consumer

This disabled-by-default runtime boundary reads one Klaviyo context page, keeps account
proof on every page, and returns transient context to a trusted internal consumer.
It does not enroll customers in a scheduler or bypass the existing fixture-only
canonical identity mapping gate. There is no live verification or profile retention.

`read_page(db, workspace_id, connection_id, generation, reader, now)` returns a
`PageDelivery(page, receipt)`, `DeferredRead(due_at)`, or `None` after completion.
The caller supplies a dedicated transaction/session and an accurate UTC clock.
After consuming a page, `acknowledge_page` advances its encrypted cursor. Without an
acknowledgement, lease expiry causes the same page to be read again; callers must
therefore consume idempotently. Receipts are not customer authorization tokens and
are never exposed through a new public route. Existing owned connection, active
integration, matching generation and encrypted grant checks guard both operations.

A durable quota is shared across all workspace connections to the same Klaviyo
account and configured OAuth client. Only an opaque HMAC is stored, keyed using the
source encryption configuration. Rotation must drain workers first; quota continuity
across encryption-key rotation is not yet implemented. Each reservation takes row
locks and commits a 120-second lease before any HTTP. At least 4.1 seconds separate
successful reads (measured again after the response), conservatively below the
documented account proof limit.
An expired lease can be reclaimed; request generation/fence checks reject late results.
The checkpoint binds encrypted cursor/receipt data to workspace, connection,
integration, generation and external account. No profile or raw account data goes in
the new tables. A maximum of 20 acknowledged pages bounds a run. Provider cursors and
small digest history exist only within the encrypted checkpoint; no profile context
is persisted. This internal page boundary does not claim an end-to-end exactly-once
canonical customer importer.

Disconnect and reconnect delete the scoped checkpoint under existing source locks,
including encrypted cursor and receipt material. An in-flight result cannot recreate
that deleted state because generation/ownership is checked again after HTTP. Each
read also prunes at most 100 expired opaque quota rows in a separate committed
transaction; only cooldowns older than one day with no active lease qualify. This
bounds cleanup work and avoids deleting an active account cooldown. Idle installations
need an operational invocation of the same cleanup function to remove expired rows.

429 responses produce a typed `CRMRateLimited` with integer or HTTP-date Retry-After
parsing (5 seconds–24 hours; malformed/missing defaults to 60 seconds). The paced
consumer measures that delay from response time and persists the shared cooldown and returns a due time without sleeping or
retrying. Account mismatch delivers no profiles. OAuth and refresh calls also return
the typed rate limit, not a revocation classification, but are not yet enrolled in
this global quota. Other applications' traffic can still consume provider capacity;
429 remains authoritative. Automatic retry scheduling, canonical consumption,
a canonical consumer lifecycle beyond disconnect/reconnect, and all-call OAuth pacing remain
follow-up work before live enrollment.

Migration `20261006_0038` descends from `0036`; parallel `0037` requires a merge
revision during integration.

Official sources checked 2026-10-06:

- [Get Accounts](https://developers.klaviyo.com/en/reference/get_accounts): 1/s burst,
  15/min steady.
- [Rate limits and errors](https://developers.klaviyo.com/en/docs/rate_limits_and_error_handling):
  OAuth quota is per account/app installation; 429 Retry-After is seconds. No immediate
  retry before the specified interval.

## Renewal Follow-Up (2026-10-06)

The durable boundary now supports Klaviyo, HubSpot and Omnisend and handles staged
renewal without resetting acknowledged cursors. Every renewal proof consumes its own
quota slot. Terminal authorization/identity failure retires the scoped checkpoint;
unknown token issuance is not replayed. See [inlet-crm-renewal.md](inlet-crm-renewal.md)
for current interfaces and failure behavior. Earlier scope limitations in this record
describe the original pacing package, not the new renewal implementation.
