# Current Social Review API — Closed Four-Case Fixture

Proposal only. Read reviewed social_producer_retained_fixture at4702e42 and
social_configuration_current_fixture at34f8317; actual implementation must branch
from their integrated successor. No producer18/configuration4 behavior changes.

```text
tests/test_customer_social_review_api.py::test_owned_exact_no_dsa_api[sqlite-meta_ads]
tests/test_customer_social_review_api.py::test_owned_exact_no_dsa_api[sqlite-tiktok_ads]
tests/test_customer_social_review_api.py::test_owned_exact_no_dsa_api[postgres-meta_ads]
tests/test_customer_social_review_api.py::test_owned_exact_no_dsa_api[postgres-tiktok_ads]
```

## Source And Database Handling

Add only closed consumer literal `api` to retained_social_producer, requiring change=None.
No child producer change. Existing producer/configuration paths remain exact. New
`tests/social_review_api_current_fixture.py` owns API expected-document/auth evidence
and delta validation, not a callback or arbitrary allowed-table argument.

A fixture restricted to originalname test_owned_exact_no_dsa_api and the existing
Meta/TikTok platform matrix calls retained_social_producer(...,consumer='api') with
actual encoded video only for TikTok. It yields a typed context containing the existing
SocialProducerSource and a single-use API-login expectation. No original runtime or
live capability crosses. load_source proves current owned immutable plan/media/native
source exactly as reviewed. Historical producer reports native_posts0; no execute step.

SQLite source intentionally creates its own exact owned current.sqlite. All test/API
Sessions must use source.engine, not the separate empty base customer_engine. A local
`replicas` fixture delegates to the unchanged identity replicas fixture implementation
using source.engine and existing monkeypatch, yielding normal TestClients/FakeProvider.
It depends on the source context so requests/clients finish before final graph check.
No changes to global replicas/customer_engine. PostgreSQL retains owned isolated schema.

## Actual Identity Without Rewriting The Retained Actor

PIN test_provider_qualification.seeded creates CustomerUser(issuer='mock',subject=actor,
email='mock@example.invalid'). Read and assert that exact retained identity from source.
Configure only this local FakeProvider instance issuer and email to the retained values;
verify it returns that issuer/subject, then call ordinary login(alice, actor+':1').
Assert returned ID is the existing actor. Login(bob,'other:1') creates a genuinely foreign
user through current API, not a seeded membership/workspace. Both remain actual current
session issuance with ordinary TTL and wall clocks. No stored issuer/subject/email edits,
no auth bypass/TTL extension. The same email does not confer ownership.

Bind a closed `SocialApiLoginEvidence` once immediately after these actual logins:
source actor, Bob ID, two session cookie digests/CSRF digests, two known token-receipt
digests, bounded before/after real issuance time. The validator reloads actual rows and
asserts known issuer/subjects/contact/status, exact user links, ordinary TTL, authenticated
and created timestamps within captured issuance interval, token expiry ordinary
FakeProvider interval. Existing actor row must remain byte-identical. Capture only the
validated exact row snapshots for later equality, never wholesale accept current tables.
No request token/cookie secret is written to logs or evidence files.

The finalizer requires Alice's exact new session alone gains revoked_at through the
original actual logout, within the recorded request interval; Bob remains unrevoked.
All other session fields and existing rows exact. Two token receipts exact (no expired
preexisting receipt cleanup assumed: verify baseline set empty for this closed source).
Exactly one new Bob user, no third user, workspace, membership or provisioning change.
Unbound expectation denies any auth/review additions rather than silently accepting them.

## Expected Social Graph — Exact Rows, Not Table Exemptions

API expected selection is computed before yielding from actual load_source and current
read-only social_review_service.selection, using existing API profile modification:
Meta dsa_requiredFalse, matching option profile digest; TikTok existing cover profile.
Requirements must retain API wording_version='contract-test-v1', requirements digest
'a'*64 and original exact wording. Existing configuration helper uses a different
wording version; do NOT mutate its default expected_document or reuse a mismatched hash.
New API-local expected document uses the same actual selection boundary, no fabricated
native/media proof. Actual runtime clock remains original NOW.

Final delta accepts exactly:

- One current SocialConfigurationReview matching the independently computed typed
  document, canonical digest and exact workspace/account/integration/draft/revision/
  actor/NOW fields; generated ID must be unique32hex.
- One explicit legacyV1 review built by the original test's deliberate historical seed:
  remove configuration/configuration_digest and requirements.wording, use originalV1
  schema, strict LegacySocialConfigurationDocumentV1 validation and its exact digest.
  Exact same scoped scalar fields and NOW; distinct unique32hex ID.
- Exactly one approval for each exact review, same actor/workspace/review digest,
  NOW confirmed_at and independently recomputed approval_digest. Repeated current
  confirmation adds no row. Wrong digest and legacy attempted reconfirmation add none.
- Exact two-login auth delta above; no other tables/fields change.

All source, media, campaign approval, mandate/ledger/reservation/execution review/run,
qualification, provider and financial graph rows remain exact; no new attempts,
responses or receipts. Schema snapshot unchanged and default advertising-write guard
still disabled at graph reads. API consumer finalizer invokes only named API validator;
producer/configuration callers retain their existing exact deltas. No blanket table
exclusions or generic callback plumbing.

## Original Test Body And Assertions

Change only source/fixture loading, engine references, removal of identity-row rewrite,
and actor-derived normal login. Original options/runtime None503, eligible label,
missing-CSRF403, forbidden-extra-field422, actual create201/nonexecutable response,
Bob403, current confirmation200/replay200/wrongdigest409 remain unchanged. Keep original
explicit legacy seed and original hash/read/status/configuration-null/reconfirm409
assertions; do not replace legacy seed with a current upgraded document. Preserve actual
logout204 and subsequent401. Original SocialReviewRuntime and media-store dependency
injection remains disclosed, no execution capability or global guard patch.

AST proof compares full post-setup body except the documented source.engine binding
and same-actor login expression; all original assertion semantics/decorators preserved.
The original user-exists setup check is replaced by stricter source identity checks.
No new privacy-erasure or live-publication coverage is claimed; Bob isolation and
historical exact-hash read are the actual current privacy/history assertions.

## Qualification Gate

First actual SQLite Meta/TikTok API2 gate, then exact4bothDB. Any source/identity/DB
or configuration selection failure preserves full trace; do not rewrite issuer/subject,
relax source-current validation or create a new financial exception. Focused pure
closed-delta negatives should prove unrelated field/row mutation rejected, duplicate
confirmation/auth rows rejected and an unbound expectation fails closed. Then relevant
producer/configuration positive compatibility (bounded), strict current deployment
boundaries, whole Ruff/bare mypy isolated/tmp and diff. Raw logs/XML and exact node
mapping retained. No aggregate, shared target reset, live call or broader consumer edit.
