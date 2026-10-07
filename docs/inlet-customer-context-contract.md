# B12 Customer Context Boundary

Klaviyo, HubSpot and Omnisend are optional read-only enrichment sources. Shopify remains
the only canonical merchandise sales ledger. Missing customer-data connections never
block advertising-only analysis. This package must not reuse the private CRM gateway
as if it were one of these provider adapters.

The shared B11 source connection supplies explicit workspace, provider, account,
integration and generation. Provider adapters normalize bounded current-profile pages
into fixed subscription/lifecycle fields; arbitrary custom properties, names, addresses,
email, phone, IP addresses, marketing text and provider-attributed revenue are excluded.
Subscription status is descriptive context, not proof of consent or permission to target.
Unknown/custom lifecycle values remain unknown rather than becoming sales.

Canonical enrichment requires verified source-to-Shopify identity. A same-looking
external ID, email or custom property alone is insufficient. The initial offline adapter
can exercise this boundary with verified fixture mappings; live mapping qualification
is a release requirement. Matching facts must still exist in the owned active Shopify
store. Suppression and retention cannot be bypassed by another provider's copy.

The initial context evaluation is transient: no raw profile pages or new contact history
are persisted. It returns bounded pseudonymous canonical-customer context and evidence
status. This avoids silently extending the approved Shopify financial retention policy
to new contact attributes. Persisted enrichment, its retention/export/erasure policy and
any private CRM gateway access remain separate design decisions. No new revenue input
or order-creation method exists, so repeated source purchases cannot add sales.

Omnisend reads only current contacts/channel status. It does not fetch synchronized
Shopify orders, infer order-state history from event definitions, or claim a full event
history export. Fixed request paths and validated cursor values prevent response links
from becoming arbitrary fetch destinations. Disabled-default Klaviyo and HubSpot HTTP transport preparation is documented in
`docs/inlet-crm-http-runtime.md`. Omnisend transport enablement remains unavailable
until its account identity/OAuth contract is qualified. Live canonical enrichment
for all three still requires verified mapping semantics and real-account validation.

Official references checked 2026-10-06:
- [Klaviyo profiles](https://developers.klaviyo.com/en/reference/get_profiles): profiles:read,
  explicit subscription fields, revision header and cursor pagination.
- [HubSpot contacts](https://developers.hubspot.com/docs/api-reference/legacy/crm/objects/contacts/guide):
  selected lifecycle property and opaque object identity; custom lifecycle values exist.
- [Omnisend contacts](https://api-docs.omnisend.com/reference/get_contacts): contacts.read,
  version header and opaque cursor pagination.
- [Omnisend channel semantics](https://api-docs.omnisend.com/reference/contacts): subscription
  status alone is not proof of consent.
- [Omnisend order limits](https://api-docs.omnisend.com/v3/reference/orders): synchronized
  ecommerce orders are not available through that order API.
