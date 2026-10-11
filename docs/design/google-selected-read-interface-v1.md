# Google Selected Reporting Read Port V1 — 2026-10-11

Next injectable acquisition seam, not a runtime default. Reuse frozen
SelectedCaptureRequestV1 and GoogleSelectedPageV1. Raw profile remains explicitv24;
this does not qualify configured v25 compatibility or imply current production use.

`GoogleSelectedHTTPRead(context_reader, transport=None, clock=UTCclock)` accepts an
immutable request and requested cursor, obtains server-owned short-lived read context
bound to request_digest, then performs only Google Ads search POSTs. Context includes
excluded SecretStr access/developer tokens, optional validated manager login and
expiry. Ownership, exact current selection/source and original session authorization
belong to the server resolver, not to caller-supplied DTOs. No resolver/default is
activated in this package and no public API accepts the context.

Each page proves exact advertiser id/resource/currency/timezone and the exact
selected conversion action resource/owner before a selected campaign/day report.
Same-customer action ownership only; unavailable manager-owned support stays explicit.
Metadata may not silently adopt request units. Query/profile/action/event/date bounds
remain exact; GAQL literals are built only from validated numeric IDs/ISOdates.
Account/action metadata queries must finish in one bounded page; unexpected further
pagination rejects rather than pretending metadata coverage is complete.

Read failures/401/403/429/outage/malformed replies are sanitized errors, never empty
successful selected evidence. Response limits and no redirects/trust-env follow
existing reads. Decode selected bytes before floating conversion; repeated cursors
reject. Empty pages still retain capture/request digest and never imply zero.
Check expiry before and after every I/O and parse. Caller performs final original-
session/source/selection/privacy checks and bounded staging/atomic publication.
No read receipt alone can qualify a capture or customer plan.

Tests use only MockTransport. They verify method/path/query restrictions, identity,
units/event owner, raw exact decimals, empty response binding, errors and mid-read
expiry. No provider call, OAuth grant, developer token setup or advertising writes.
This exact query/API combination still requires permitted provider qualification
before any live-support claim, separately from deterministic adapter tests.
