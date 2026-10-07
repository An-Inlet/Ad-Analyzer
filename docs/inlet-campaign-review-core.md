# Campaign Review Core — B14 First Package

This package provides offline campaign review APIs and private **development** media
storage. It does not publish campaigns, reserve spend, fetch landing pages, call a
provider, or make Inlet production ready. `publication_eligible` is always false;
`approved_for_offline_plan` records approval of the exact immutable review artifact.

## Frozen Core Interfaces

`app/campaign_review/contracts.py` defines `RevisionInput`, the discriminated content
union, `MediaRef`, `ReviewArtifact`, `ExactApproval`, and `MediaStore`.

- Revision inputs bind the workspace-owned advertising account/integration, current
  approved mandate revision, currency, total modeled campaign exposure in micros,
  and aware start/end timestamps. Budget is an allocation ceiling within the mandate,
  not permission to enlarge it. No reservation or execution occurs during review.
- Content kinds are `google_search_v1`, `meta_website_sales_image_v1`, and
  `tiktok_website_conversion_video_v1`. Unknown kinds/fields are rejected. These are
  narrow offline shapes, not provider-qualified campaign publication manifests.
- A canonical domain-separated SHA-256 digest covers the complete artifact,
  revision, workspace, account/mandate definition, explicit connection id/generation,
  and immutable media references. Approval requires the exact current revision and
  preview digest. An edit always creates an unapproved revision; historical approvals
  remain attached only to their original immutable content.
- `MediaStore.put_if_absent(workspace_id, sha256, size, chunks)` and
  `read_exact(workspace_id, sha256, size)` never accept a URL. The current development
  implementation uses workspace directories, immutable content-addressed files,
  exclusive creation, no-follow directory/file opens and hash/size verification.
- Meta adds an explicit generation (migration 0037), incremented only after verified
  reauthorization of an existing connection. Ciphertext rotation is not review identity.
  Existing Google and TikTok generations are reused.

Review and approval recheck current membership at the API boundary and current
workspace/integration/account, paid-work rollout gate, confirmed goal/approved mandate,
mandate expiry, budget and schedule bounds, connection status/generation, and exact
media bytes. This does not substitute for fresh measurement/spend evidence at the
future publication claim. A stale or unsupported publication capability remains gated.

## API And Storage

Under `/api/customer/v1/workspaces/{workspace_id}`:

- `POST /media`: authenticated owner/admin raw-byte upload with CSRF/origin checks.
- `GET /media`: scoped library metadata, bounded to the development quota of 100 objects.
- `GET /media/{media_id}`: authenticated scoped bytes with no-store/nosniff/CSP headers.
- `POST /campaign-drafts`: create an immutable initial revision.
- `PUT /campaign-drafts/{draft_id}`: compare expected revision and append a revision.
- `GET /campaign-drafts/{draft_id}/preview`: exact structured review artifact and digest.
- `POST /campaign-drafts/{draft_id}/approve`: current exact digest/revision approval.

Default storage is disabled. Explicit local development configuration uses
`AD_ANALYZER_MEDIA_STORAGE_MODE=local_dev` and an absolute private directory in
`AD_ANALYZER_MEDIA_LOCAL_DIRECTORY`. No cloud resources or public URLs are created.
Static JPEG/PNG are decoded and verified using the explicit Pillow dependency:
8MiB file, 16 million pixels, one frame; no SVG or arbitrary active content. Library
limits are 100 objects and 128 MiB per workspace, serialized under the workspace lock.
These are engineering development limits, not commercial storage entitlements.
Local file access is bounded and integrity checked, but is not cloud durability,
backup, malware certification, rights verification, or lifecycle/deletion orchestration.
Server administrators must keep this development directory private.

Google text and Meta supplied image drafts can receive meaningful offline approval.
TikTok video remains blocked with `video_validation_unavailable`; no uploaded image
is passed off as a validated video. The structured preview is not yet a rendered
customer portal screen or a provider placement preview.

## Evidence And Remaining Packages

Focused suite: 61 passed, 1 skipped (the PostgreSQL concurrency test's SQLite variant),
covering real mandate/goal/account bindings, edits and stale approvals, ownership,
CSRF/roles, entitlement gate, exact media integrity, unsupported kinds, Meta generation
reauthorization, and concurrent PostgreSQL edits. Ruff and mypy 276 source files pass.
Migration 0037 upgraded a new disposable PostgreSQL database and round-tripped
0037→0036→head. Whole-repository `alembic check` still reports unrelated existing CRM
metadata imports and analysis enum-type drift; no B14 table drift was reported.
Full and hosted CI for this package are pending; no behavior is live verified.

Next B14 work: bounded video validation/processing, rendered versioned customer review,
private production MediaStore and deletion/quarantine lifecycle, compiled publication
plan/capability interface and exact preview-to-publication equivalence fixtures. B15/B16
must add separately approved publication orchestration, stable resource reconciliation,
freshness checks and spend reservations; none are implemented in this package.
See `inlet-campaign-review-contract.md` for the full proposed dependency contract.

## Google Copy Bounds And Publication Prerequisites

Google supplies three to 15 RSA headlines and two to 4 descriptions. Headlines are
bounded to 30 units and descriptions to 90, counting East Asian wide/fullwidth characters
twice; keywords are bounded to 80 characters and 10 words. Dynamic insertion syntax and
duplicate supplied strings are outside this initial literal-copy contract. These offline
checks do not claim to implement Google's entire editorial/provider validation policy.
Sources checked 2026-10-06:
[Google RSA overview](https://developers.google.com/google-ads/api/docs/responsive-search-ads/overview),
[Google RSA character limits](https://support.google.com/google-ads/answer/7684791?hl=en),
[Google keyword system limits](https://developers.google.com/google-ads/api/docs/best-practices/system-limits),
[Google keyword word limits](https://support.google.com/google-ads/answer/7337243?hl=en).

This subset does **not** freeze a complete B15 PublishPlan. Tracking, account-owned
conversion identifiers, bidding configuration and a qualified versioned capability
manifest are absent. Each is an explicit publication prerequisite; no publisher may
invent or append such fields after approval. Adding any publication-affecting field
must create a new revision, new preview/digest and new approval. Concrete provider
mapping and exact preview/plan equivalence must be reviewed before B15 work starts.
