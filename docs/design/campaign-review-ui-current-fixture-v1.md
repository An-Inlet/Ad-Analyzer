# Current Campaign Review Browser — Closed Two-Case Source

Docs-only proposal, no implementation or tests. Exact original failed identities:

```text
tests/test_campaign_review_ui.py::test_review_browser_real_api[sqlite]
tests/test_campaign_review_ui.py::test_review_browser_real_api[postgres]
```

Unlike Social Configuration, actual `/app/campaign-review` still returns current
`campaign-review.html` with offline planning controls. Keep current HTML, modules,
APIs and full `tests/javascript/campaign_review_browser.mjs` unchanged. Its SHA256
is `cd2b640fda40c0f8ef98ad2f555135d5ed6318c55c59fe5f661f46cf530e8c82` and its diff
against PIN2155ff3 is empty. No retained HTML, driver slicing or product restoration.
Existing `test_review_shell_and_assets` remains current and checks CSP/no-store/assets.

## Why The Existing Single-Provider Source Is Insufficient

Original setup calls `test_google_action_plans.setup`, which approves a legacy
mandate, then creates a customer owner and adds Meta101/TikTok202 sources. It appends
both accounts to the same policy, edits/reapproves that policy, and only then uploads
an image and creates two offline drafts. The existing campaign_review retained
helper replaces the policy account list with one provider; invoking it three times
would not preserve this one-workspace/one-mandate ordered three-account binding.
Do not extend that helper with arbitrary policy callbacks or mutate approval in the
current runtime. Existing campaign21 and single-provider defaults stay unchanged.

## New Closed Original Prefix

New test-only `campaign_review_ui_retained_fixture.py` and one literal driver
`tests/fixtures/retired_execution/campaign_review_ui_seed_driver.py`, registered as
closed SourceLifetime profile `campaign_review_ui`. Use exact PIN
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`. Reference original test source SHA256:
`37086bd66799c79679075a7b395d83c7f079def8fea8c8fd044a8445eb867b7a`.

Driver has no modes, arbitrary callback/import path, current capability overrides,
media factory or network adapter. It performs the literal original prefix through
`mandates.approve(...); db.commit()`, stopping BEFORE image upload/draft creation:

1. Original configuration fixture and genuine `test_google_action_plans.setup`.
2. New UUID customer with original issuer, subject `review-owner`, email
   `review@example.invalid`; actual owner membership in the same workspace.
3. Original active Meta integration/account101/USD/UTC and MetaConnection, original
   TikTok integration/account202/USD/UTC/connected generation1/NOW source window.
4. Actual original policy append in exact order Google, Meta, TikTok; genuine edit
   and approval by that actor at original NOW. Preserve100 total/80 per-action/50
   positive-change caps, period, allowed actions, account ownership and audit chain.

Return only frozen `CampaignReviewUiIds`: workspace_id, actor_id, mandate_id,
mandate_revision, mandate_policy_digest, google/meta/tiktok account IDs and integration
IDs, Google/TikTok source UUIDs, Meta positive source integer, provider_posts literal0.
No ORM/runtime/authority object crosses. IDs have strict bounded types, exact JSON
keys and maximum8192-byte output checked BEFORE parsing. Parent re-reads owned actual
rows/current policy/digest and exact ordered scope tuple in a fresh Session.

Both parent and child validate the exact owned disposable target before DB I/O:
SQLite plain/noquery absolute regular nonsymlink `artifacts/current.sqlite`; same
resolved path including all parent directories; PG validated loopback disposable URL,
no query, exact engine URL, literal `inlet_test_<32hex>` current schema. Both check ALL
current tables empty except alembic_version before producing. Current schema is never
replaced. SourceLifetime covers extraction/child/reaping/cleanup; persist IDs/logs.
Zero posts is source-established (no constructed transport), not a fabricated server
counter. Optionally forbid HTTP transport construction in the child, without replacing
any product capability guard. Assert no execution mandates/consents/reviews/actions/
attempts/reservations/responses/receipts before and after current consumer.

## Current Setup, Identity And Full Browser

Parent fixture yields typed source(engine, ids, store, evidence). Use source.engine
for all current DB/API/media operations and close/dispose only after browser/listener
shutdown. Actual current image `service.upload(png())` and the original two
`service.revise` calls remain CURRENT, not child-produced. Preserve original exact
Meta image definition and Google definition; record typed expected inputs before
writes and validate exact resulting artifacts/digests/source bindings.

No stored identity rewrite. The full driver already signs in as review-owner:browser.
Configure only local FakeProvider issuer/email from the verified retained user,
keeping original subject/token literal, ordinary real session TTL and real auth clock.
One actual normal login, one token exchange receipt, existing actor; no logout exists
in this driver, so final session stays unrevoked. No new user/workspace/membership.
Use single-use response-time binding of exact session/CSRF cookie digests and bounded
real issuance/auth/token-expiry timestamps, comparing the entire original snapshot.
Keep source issuer/subject/email immutable. No simulated auth dates.

Preserve original local JourneyClock only on `customer_campaign_review.datetime`,
original NOW, actual media endpoint/bytes, and unchanged60sec browser completion.
Original harness media-denied toggles still return503 and original viewer endpoint
changes only the exact owner membership role to viewer. This membership model has no
updated_at field; no blanket timestamp allowance. Driver behavior stays complete:

- Current real upload, TikTok draft creation/playback64px/blob revocation on denied
  media; Google and Meta draft creation, each unapproved; exact image decoding4px.
- Denied image prevents acknowledgement-based approval; Google exact60micros display,
  supplied copy, no supplied media required and explicit publication-disabled message.
- Explicit offline approval of original Google revision1 without changing its digest.
- XSS text edit creates revision2 and invalidates approval; actual concurrent PUT
  creates revision3; stale approval rejected/cleared; reload then viewer-role denial.

Only existing workspace/draft placeholder substitution remains. Do not change source
periods, account ordering or selectors to accommodate a failing current API.

## Closed Current Graph Delta

Snapshot the COMPLETE graph/schema immediately after authentic prefix. Current setup
and browser expected changes are explicit; no blanket table exclusions. A typed
one-shot setup binding validates current image+two drafts, then exact auth binding.
Final validator additionally requires original prefix snapshot equality and permits:

- Exactly two media rows: actual supplied PNG and encoded MP4. SHA256/size/MIME/
  dimensions/creator/workspace/NOW derived from exact supplied bytes and independent
  current media inspection. Read stored bytes back and compare, not merely row hashes.
  Original image is immutable; browser adds one video. No other media/file authority.
- Exactly five drafts: original Google/Meta plus browser-created TikTok/Google/Meta.
  Original Google head becomes3; all other heads remain1. Exactly seven revisions:
  original Google1/2/3, original Meta1 and three new1s. Resolve generated UUIDs only
  through unique exact typed expected definitions; no name-only proof or arbitrary
  accepted browser payload. Expected browser definitions are frozen before the driver
  from its literal values/account order/mandate period/media hashes, including local
  date-input roundtrip semantics; no freeform numerical policy interpretation.
- Validate canonical ReviewArtifact for each exact definition/revision/source and
  recompute fingerprint. Expected artifacts may be reconstructed by current pure/read
  artifact builder with known typed input plus validated row ID, never by accepting
  row.artifact itself as expected data. Exact actors/NOW and scoped IDs required.
  Only original Google revision1 has approved_by=actor/approved_at=NOW; all others
  null. Original Google1 artifact/digest unchanged by approval. Revision2 and3 share
  definition but differ bound revision/fingerprint. All source provenance remains exact.
- Exactly one current real session/token receipt as bound; remains unrevoked. Only
  exact customer membership role owner→viewer, every other column unchanged. No new
  social configuration records, approved legacy policy, execution authority or effects.

Supplement actual browser assertions with copied-graph negatives: original source/
auth mutation, unexpected session/draft/revision/media, foreign scope, changed media
bytes/hash, extra approval, wrong head, wrong role and unbound/repeated binding.
Do not invent positive proof from a copied row. If ordinary current setup changes an
additional automatic field, preserve failure and propose exact validated delta first.

## Qualification And Limits

After review: SQLite one-case gate, exact browser2 plus unchanged shell/assets1;
bounded current campaign-review positive/scoped binding and default planning boundary
compatibility. No Full, aggregate, provider/live calls or historical batch rerun.
Whole Ruff/bare mypy/Node/diff at final source; original full JS equality proof.
Unique /tmp basetemps with durable workspace logs/XML, source IDs, failed/current
artifact manifests before checkpoint. Preserve every failure rather than relaxing
ownership, entitlement, freshness, body assertions or source guards. Existing SQLite/
PG and source setup limitations remain explicit. Only two original identities receive
recovery credit; supplementary tests overlap existing packages.

Current customer product credit is offline planning/review/media behavior only.
The authentic approved legacy source is compatibility provenance, not a new current
spending authorization or proof that the product can publish advertising.
