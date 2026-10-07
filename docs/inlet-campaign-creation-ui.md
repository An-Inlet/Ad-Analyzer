# Customer Campaign Draft Creation

The customer application’s existing `/app/campaign-review` page now supports
creating Google Search text, Meta website-sales image, and TikTok website-conversion
video drafts from supplied content. It reads existing approved, unpaused simulation
mandates and their account scopes. It does not create/approve mandates, connect
accounts, generate creative, or authorize live spending. Provider readiness and
current mandate dates/limits remain authoritative server checks.

Owners/admins supply name, HTTPS destination, modeled exposure, local-time schedule,
country/language codes, and platform-specific copy. Google uses supplied headlines,
descriptions and exact keywords. Meta/TikTok use Shop Now and validated private
media. Account scope, mandate ID/revision, media ID/hash, and exact saved revision
are preserved internally. The API currently exposes mandate account scopes rather
than friendly account names; choices identify platform and position within that
mandate, with exact identifiers available in the review reference.

A raw-byte upload uses the existing same-origin CSRF-protected media endpoint.
The server validates actual bytes; browser size/type hints grant no authority.
The user can reuse up to 100 listed validated media objects or upload new media.
Workspace switches reset media choices and form state. Saving creates a draft,
then loads its exact review; it never automatically approves it. Existing review
consent and current-revision approval rules remain unchanged.

Video playback fetches private bytes with same-origin credentials and denied
redirects. Stream consumption is capped at 64 MiB with a 30-second fetch deadline.
It uses a local object URL, revoked when the scope/revision changes. Approval only
becomes available after `loadeddata`, not merely metadata; errors clear readiness.
Playback has controls and does not autoplay. CSP adds only `media-src 'self' blob:`;
script, connection and frame restrictions remain in force. MP4 playback does not
claim provider certification or full customer-environment qualification.

Offline evidence: real HTTPS browser/API journey on SQLite and disposable
PostgreSQL creates all three campaign kinds, uploads an actual synthetic H.264 MP4,
loads decoded video frames, checks failed media response blocking and object URL
revocation, then exercises existing exact approval/stale revision/role revocation.
Pure Node checks cover monetary precision, content composition, media-kind mismatch,
and bounded stream rejection. API/service regressions cover existing ownership,
CSRF, decoder, and exact-review behavior. No provider requests or real customer
media were used. Hosted CI and deployment qualification are separate gates.
