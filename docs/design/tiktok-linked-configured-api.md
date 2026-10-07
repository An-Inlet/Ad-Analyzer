# Configured Linked Push Customer Flow

The new `/execution/tiktok/linked` namespace is separate from historical social
configuration v1/v2. Existing source campaign drafts/media and separately approved
production mandates are reused. No new table or migration is planned.

- `POST /options`: existing CatalogIntent `{draft_id,draft_revision}`. Returns
  `{name,environment,options:[{id,name,requirements_text,review_available}],blockers}`.
  IDs are opaque server commitments, not native identity/pixel IDs.
- `POST /reviews`: LinkedPushReviewIntent adds `option_id`, owned
  `cover_media_id`, and answer `{kind:"tiktok_linked_push",reviewed_video_and_cover:true,
  commercial_music_rights_reviewed:true,creates_new_linked_post_reviewed:true,
  ads_only_visibility_reviewed:true}`. No hidden/default consent.
- `GET /reviews/{id}`: owned safe review summary, exact digest and confirmation.
- `POST /reviews/{id}/confirmation`: `{expected_digest,acknowledged:true}`.
  Refresh capability observations but retain the originally reviewed document;
  renewed timestamps alone never change consent or force another review.
- `POST /creation-reviews`: existing SocialCreationIntent with the exact linked
  configuration review/digest plus production mandate ID/revision. Fresh genuine
  qualification and exposure remain required; no inferred spending permission.
  Returns existing ordinary execution review view. Approval/run/advance and
  activation remain separate customer actions on existing execution endpoints.

Server configuration uses a separate pinned
`inlet.tiktok-linked-push-configuration-bundle.v1` schema with explicit TT_USER,
ads-only ON, existing bounded numerical profile fields and exact reviewed wording.
Old v1 bundle hashes do not change. BC and Pull creation are not enabled by this
slice. The original evidence registry remains empty by default.

The catalog uses actual owned identity/get, identity/info and advertiser/info
readers; pixel/event and financial qualification remain separately registered
contract-scenario evidence with their existing blockers. It does not claim live
native pixel qualification. No capability HTTP runs inside economic/DB locks.
An original-session-bound request refreshes outside locks, then a pure snapshot
validator runs at every forward boundary. Source/generation/media/profile changes
invalidate the flow. Historical reconciliation uses original attempts instead.

This document freezes the intended dependent API interface. Implemented service
checkpoint is cbf9a69; configured API/browser acceptance is not yet complete.

## Configured Backend Checkpoint — 2026-10-07

The ordinary configured dependency now produces linked Push choices using actual
owned identity-list, identity-info and advertiser-capability GET adapters. The
pixel catalog remains explicitly registered decoded contract evidence, never
native financial qualification. New linked bundle pins are explicit; no default
runtime, source, profile or live admission was installed. BC publishing remains
unavailable without independent owner permission. Pull catalog is a separate
read-only package; this customer mutation profile is TT_USER Push, Ads Only.

The stored new-schema document additionally binds `identity_label`, obtained from
the server-owned named choice. Browser input cannot supply it. Original observation
clocks and digests remain immutable; confirmation and every forward boundary read
fresh capabilities outside DB locks, then bind a pure local current-facts check.
A normal time advance between prepare and confirm is supported.

Safe review JSON includes id/digest/environment/confirmed/option_id, campaign
(name/start/end/currency/budget), media.video and media.cover exact owned bindings,
approved creative content, safe configuration fields, identity_label and the exact
requirements wording. Native identity/pixel/location identifiers and capability
proof digests are excluded from this configuration projection. Generic separately
approved execution views retain their existing owned-reference projection.

Separate activation uses its own linked adapter and original linked readback digest.
Only exact status changes are emitted, campaign last. Unknown outcomes keep the
original attempt and reservation; historical reconciliation does not require a
still-current configuration approval. New legacy CUSTOMIZED_USER forward creation
remains prohibited, while old request/readback contracts remain readable.

### Checks Actually Run

- `/tmp/inlet-linked-configured-first.log`: actual ordinary configured API complete
  creation and separate activation, SQLite + PostgreSQL: 2 passed (overlap below).
- `/tmp/inlet-linked-configured-cohort.log`: 27 cases, 25 passed / 2 failed. The
  failures were missing cover files raising FileNotFoundError at linked selection.
  Fixed the exact media-read boundary to sanitized 409; no weakened assertions.
- `/tmp/inlet-linked-configured-boundaries.log`: both failed media cases plus eight
  permission/session/source-generation/explicit-rights negatives: 10 passed.
  Combined these establish 18 distinct configured API cases and 17 contract/export
  cases passing. Actual HTTP is MockTransport; no live qualification is claimed.
- Whole Ruff, mypy application plus configured fixture/API tests (519 source files),
  Node syntax and git diff checks are recorded with the final local commit.

`tests.tiktok_linked_runtime_fixture.configured_linked_customer` returns the same
fixture tuple as the earlier configured TikTok fixture. It uses actual owned source,
session, vault, media, consent and ordinary runtime factory; only identity and
provider wire transports plus explicitly labelled scenario evidence are injected.
No execution records are seeded and no runtime getter is overridden.

Actual HTTPS customer UI acceptance is a separate parent-owned successor and is
pending at this backend checkpoint. Existing positive future-creation fixtures
that still use CUSTOMIZED_USER need explicit migration; they are not claimed green.
