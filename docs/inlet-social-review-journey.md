# Exact Social Configuration Review

This offline package builds on0059's owned review/approval tables. It adds an actual
customer configuration-review API and page, not a configured social execution
service. Both new discovery runtime and existing execution runtime default to
unavailable; there is no provider credential factory, live activation or new spend
permission. TikTok native discovery and social qualification blockers remain.

## What The Customer Can Review

`/app/social-configuration` selects an owned, approved campaign and an opaque named
configuration supplied by a server-owned catalog. Meta requires an explicit
special-category answer; applicable/unsure cannot confirm. Only verified no-DSA
profiles are eligible; beneficiary/payor input fields do not exist and extra fields
are rejected. Missing server-reviewed requirements make an option unavailable.

TikTok pairs the exact supplied video with an owned uploaded image. Private bounded
same-origin bytes are rendered through revocable blob URLs. Confirmation requires
actual video loadeddata/image load, not metadata-only success. Changing the cover,
answer, option, campaign or workspace invalidates local acknowledgement; logout
clears the previews and rendered review. This page reuses the media library; the
existing Campaign Creative page supplies media upload.

The exact review shows source campaign/period/landing page, reviewed requirement
text, countries/languages, budget semantics, time zone, attribution, placement,
bidding and supported switches. Confirmation records this configuration only.
Separate production consent, exact execution approval and native qualification
remain necessary. Default-unavailable configuration is displayed honestly.

## Stable Customer Boundary

All routes below are under `/api/customer/v1/workspaces/{workspace_id}/execution/social`:

- POST `/options`: owned approved draft ID/revision. Resolves server profiles,
  rules and named catalog, then rechecks original session/source after provider IO.
- POST `/reviews`: draft/revision, opaque option ID, strict explicit answer and
  optional owned cover ID. No caller-provided proof, runtime, configuration, hashes
  of media, rule profile or provider resource identifiers are trusted.
- GET `/reviews/{id}`: current authenticated owner reads exact history. History is
  never labeled currently executable, even if a confirmation exists.
- POST `/reviews/{id}/confirmation`: exact expected digest and explicit true
  acknowledgement. Re-resolves current catalog/profile/rules/media/source before
  persistence, holding the existing original-session authority boundary.

Mutation routes require same-origin CSRF. The injected server runtime uses real
ports; synthetic test factories are explicitly contract_test. No default catalog
or regulatory determination is invented.

## Canonical And Historical Binding

New `SocialConfigurationDocument` is version2. It persists strict no-personal-name
canonical configuration, its complete digest, exact media pair and reviewed rule
wording. The typed configuration itself rejects DSA names. The server preview
method constructs fields only; it does not fabricate an approval audit ID or emit
an executable plan. Confirmed declaration values come from the owned database
reader, including original confirmer and UTC confirmation time.

Optional `SocialPublicationReview.configuration_review` binds review ID, exact
review digest and approval digest into canonical review/plan hashes. Only this
new optional field is omitted when absent. All existing explicit null fields stay
unchanged; captured old Google and social review/plan hashes are regression tested.

Version1 configuration history remains strictly parseable/exportable with its old
hash. Missing complete configuration commitment or wording cannot be filled in to
upgrade an old approval. It requires a new review before forward authority.

Coordinator prepare, approval, claim/final locked-run admission and activation's
current checks validate persisted owner/scope/source/configuration/approval binding.
Live social plans without a reference are denied; referenced plans in any environment
require a configured current-profile/catalog validator. That callback is pure local
validation of already-refreshed server state; it must not perform provider IO under
economic locks. The separately integrated final credential-context/session fence
remains intact. Legacy unreferenced contract fixtures remain compatible, not a live
or customer bypass.

## Remaining Work

The new API records exact social configuration; the existing customer execution
creation endpoint still supports Google only. Wiring confirmed social configurations
into that intent path requires real current catalog/profile and native qualification
producers. Do not advertise this package as live social creation or purchasability.
The public marketing page is unaffected.

Personal DSA capture remains blocked pending the reviewed closure-safe privacy
contract covering all original/activation plan and request copies. No erasure
representation, retention exception, closure policy or financial-release shortcut
is implemented here. See `inlet-social-declaration-privacy-lineage.md`.

Validation is offline against synthetic data, mocked providers and disposable SQL;
actual browser playback demonstrates local browser compatibility, not provider
acceptance or a production media environment qualification. Root owns assembled
Full/CI and any future authorized live qualification.
