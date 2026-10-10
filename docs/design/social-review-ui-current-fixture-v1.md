# Social Configuration Browser — Closed Current Four-Case Fixture

Docs-only proposal after owner resume, based on reviewed1370c67 source/API helpers.
Implementation will use the integrated successor containing those helpers. No tests or
code run/changed in this proposal. The restart wiped /tmp: temporary caches, databases
and artifacts there are not claimed preserved. Workspace source/evidence is intact.

## Exact Original Scope

```text
tests/test_customer_social_review_ui.py::test_social_review_real_browser[sqlite-meta_ads]
tests/test_customer_social_review_ui.py::test_social_review_real_browser[sqlite-tiktok_ads]
tests/test_customer_social_review_ui.py::test_social_review_real_browser[postgres-meta_ads]
tests/test_customer_social_review_ui.py::test_social_review_real_browser[postgres-tiktok_ads]
```

These are full actual HTTPS Chromium journeys, not the API4 or configured feedback
browser. Shared tests/javascript/social_configuration_browser.mjs stays byte-identical.
No production changes, live calls, advertising writes, aggregate or broader consumers.

## Actual Original Behavior

The driver performs normal browser login, workspace/draft selection, actual preview
and social options HTTP requests, explicit Meta declaration or TikTok cover selection,
actual media decoding, current review creation, exact acknowledgement/confirmation,
changed declaration/cover invalidation, source-period expiry, media clearing and logout.
It checks literal rendering of workspace.name='<img src=x>', no inferred declaration,
readable modeled lifetime budget/targeting/period/environment, and No Ads Were Published.
TikTok additionally proves actual video playback and image decoding. It does not seed a
legacyV1 review, create Bob, or exercise a missing-CSRF negative; do not claim API4's
extra cases. Real mutating HTTP requests still use the product's CSRF handling.

Original Python setup rewrites issuer/subject, creates a separate SQLite closure.sqlite,
and invokes obsolete fixture(). Replace those only. Preserve its deliberate local
ReviewClock for customer_campaign_review.datetime and SocialReviewRuntime clock, initial
NOW and explicit NOW+2days expiry endpoint. Do not substitute auth/global time or alter
source timestamps/session TTL. Existing60sec completion bound and JS polling remain.

## New Closed Source Interface

Add consumer Literal 'ui' to retained_social_producer, requiring change=None. Existing
producer/configuration/api defaults and validators remain unchanged. Add separate typed
optional ui_evidence (defaultNone), owned by new
`tests/social_review_ui_current_fixture.py`; do not generalize API evidence with flags,
row counts, arbitrary callbacks or table exemptions. No child producer change.

A fixture restricted to originalname test_social_review_real_browser and platform
Meta/TikTok creates retained source with actual encoded TikTok video, uses source.engine
for all DB/API operations and owns disposal. Test removes duplicate SQLite creation and
conditional disposal. Existing factory/database generator and original DB/provider/
media/runtime dependency injection remain disclosed. No execution capability override.

The UI expected document is computed before yielding by actual load_source/current
selection using the original Meta no-DSA profile/option adjustment, or TikTok exact cover,
with wording_version='browser-test-v1', original wording and requirements digest.
API contract-test-v1 and configuration explicit-test-rule-v1 defaults stay untouched.
No document/hash is derived from later browser-written rows as its expected proof.

Construct SocialUiEvidence with the exact source actor/document and deep-copied entire
original graph, including auth rows, before yielding. Require baseline sessions/token
receipts/social configuration reviews/approvals empty for this closed source. Final
validation requires its original snapshot equal the retained context's before snapshot;
never silently accept changes before login binding.

## Identity And Actual Login Evidence

Read/assert retained CustomerUser issuer='mock', subject=actor UUID and original email.
Configure only the local FakeProvider instance's issuer/email to those exact values.
Replace exactly one served-driver literal 'social-owner:browser' with JSON-quoted
actor+':browser'; preserve every other driver statement and assertion, including all
existing workspace/draft/platform placeholders. No source user/subject/email rewrite.

Browser POST creates the ordinary real session. The existing harness response recorder
adds one narrowly scoped observation: only actual successful POST
/api/customer/v1/session response-start may call named
`ui_evidence.record_login(source, response_headers, request_started, response_started)`.
It observes actual Set-Cookie values in memory, validates single session/CSRF cookies,
and retains only their digests. Never serialize cookie secrets or fabricate a response.
The application has already committed its login before response-start; load actual rows
from source.engine in a fresh Session. No I/O/auth guard substitution.

Single-use binding requires exactly one new session for original actor, exact cookie/
CSRF digests, ordinary TTL, created/authenticated times within real request bounds,
no initial revocation, exactly one known token receipt digest(actor+':browser') with
FakeProvider's ordinary3600sec bounded expiry. Existing user bytes remain unchanged.
No new user, Bob, workspace, membership or provisioned resource. Compare the entire
post-login graph to original plus only these validated additions and the exact workspace
name change below. Refuse a second login binding or any unexpected row/field.

## Exact Final UI Delta

Allow only these independently validated changes to the full original graph:

- Original owned workspace row's name becomes exactly '<img src=x>'; all its other
  columns and every other workspace remain exact. Preserve the actual original test
  SQL assignment and user-facing literal-rendering assertion, not sanitized fixture data.
- One current SocialConfigurationReview with exact precomputed typed document/digest,
  actual generated unique32hex ID, original account/integration/draft/revision/actor and
  NOW timestamp. One exact matching approval at NOW with recomputed approval_digest.
  Changed Meta declaration/cleared TikTok cover is UI-only after confirmation: it must
  not create a second persisted review/approval. No legacyV1 row is expected here.
- The one bound actual browser session retains all fields except revoked_at from
  actual logout, bounded by real request-start/end time. Token receipt exact; no other
  auth change. Auth clock stays real even after review clock moves NOW+2days.

All original financial/source/media/campaign/mandate/ledger/run/review rows remain
exact, no new attempts/responses/receipts, physical schema unchanged and native_posts0.
Unbound evidence rejects additions. Record only exact successful login and logout
responses; missing or unexpected response means fail closed, not relaxed validation.
Media responses and HTML are the actual app responses. Harness doesn't fake completion.

Supplemental adversarial-copy checks (no DB changes) should reject altered original
auth snapshot, wrong workspace/name/extra field, duplicate review/approval/session,
wrong cookie/session actor and unbound evidence. Keep producer/config/API validators
independent and unchanged. Source finalizer runs after browser/thread/listener shutdown.

## Preserved Assertions And Qualification

All original Python browser completion/result assertions, TLS/listener/process cleanup,
response recording, media and expiry behavior remain. Only obsolete user-exists setup
is replaced by stricter identity checks; workspace-exists setup remains. AST/source
proof includes shared JS byte equality and exact served-literal-only substitution.
Additional HTTP response-status evidence may substantiate original preview/options
expiry path, but never count an early setup failure as successful expiry coverage.

First SQLite Meta/TikTok2 gate, then exact4bothDB with bounded API4/configuration
positive compatibility and default boundary checks. No broad producer18 rerun required
unless its actual shared branch changes beyond closed literal/defaultNone extension.
If native/profile/period/media/readiness fails, preserve stage/rawtrace for review;
no guard, time/TTL/timeout or assertion relaxation.

Use explicit unique /tmp basetemps if capacity requires, and copy structured browser
results, failed artifacts and unique proof/source-ID manifests durably under workspace
evidence BEFORE checkpoint or cleanup. Keep raw logs/XML outside /tmp from the start.
Prior wiped /tmp evidence cannot be recovered by assertion. Whole Ruff, bare mypy with
fresh explicit cache, unchanged-driver Node syntax and diff check before code freeze.
Only four exact original passing identities may add recovery; gates/compat overlap.
