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
