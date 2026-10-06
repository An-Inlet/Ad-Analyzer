# B14 Shared Interface Proposal

Status: design only, October 6, 2026. No implementation, schema migration, storage
provisioning, provider call or publication is authorized by this document. Read
against PR84 head `68c9bc58f9d337296d1421e966f7867027239c36`; integrate subsequent
review repairs before implementation. Executable live eligibility remains empty.

## Audit Baseline And Bounded Scope

The supplied audit's exact B14 requirement is: “Build supplied-media library and
versioned campaign review. Changes invalidate approval and previews match
publication.” Dependencies B03/B07. B15 requires reviewed Google publication with
partial-resource reconciliation preventing duplicate launches (B08/B14). B16
requires Meta/TikTok actions and reviewed publication, with every declared campaign
type passing its complete journey (B07/B10/B11/B14).

The draft contains platform, objective, landing page, audience, copy, supplied
media and budget. Review applies to an exact immutable version. Processing,
validation, platform resource creation, partial failure recovery and stale-data
stops are required. Existing human Creative concepts (`app/intelligence/schemas.py:Creative`,
campaign-scoped title/audience/hook/visual-style metadata) are not an asset library.

Use the repository's proposed `docs/inlet-campaign-scope.md` matrix, without
expanding it or claiming its live qualification:

| Discriminator | Proposed MVP Content | Explicit Exclusions |
| --- | --- | --- |
| google_search_v1 | Standard Search; supplied text, reviewed landing page and bounded keyword/audience configuration | Shared budgets, Shopping, Performance Max, feeds, unsupported bid strategies |
| meta_website_sales_image_v1 | Standard auction website sales; supplied static JPEG/PNG and reviewed campaign/ad-set/ad settings | Dynamic/catalog/carousel/generated creatives, unsupported budget owners/objectives |
| tiktok_website_conversion_video_v1 | Standard auction website conversion; supplied MP4 and reviewed campaign/ad-group/ad settings | Spark/creator authorization workflows, generated video, unsupported bidding/objectives |

Each discriminator has a versioned capability manifest. Initial runtime eligibility
is false for all three. A manifest enumerates exact allowed objectives, fields,
audience/placement/budget owners, required account-owned conversion/tracking IDs,
API version, media constraints and qualified action types. Adapter qualification
fills those values from official documentation and fixtures; unknown values reject
instead of passing arbitrary provider JSON. Engineering input caps below are not
claims about provider maxima. The matrix's live pilot approval remains an owner gate.

## Reuse And Missing Infrastructure

Reuse FastAPI, python-multipart, Pydantic StrictModel (forbid extra), SQLAlchemy,
Alembic and PostgreSQL compound ownership keys; current customer session/CSRF/
owner-admin controls and account/integration validation. Reuse workspace-lock order,
versioned mandates, exact action review, spend reservations, request keys, dispatch
fences and uncertain-outcome reconciliation. Reuse hashlib/JSON canonical digest
helpers with a new domain-separated schema version. Existing `MandateAction` is a
review/execution record; `ActionDraft.payload` is flat and limited to 8 KB, so it
must hold typed references/digests rather than an entire nested publication plan.

No reusable media/object storage, upload pipeline, media decoder or provider asset
publisher exists in inspected app dependencies. Google Pub/Sub, Secret Manager and
Firebase Admin are not media stores. Do not put media bytes into Secret Manager,
existing token vaults, public static directories, or the main SQL row. Define a
storage port; implement an isolated temporary/local test store first. A private
GCS implementation is compatible with the existing cloud direction but requires an
explicit dependency, private bucket/region/retention decision and separately approved
provisioning/IAM. Do not rely on a transitive storage client or assume it is deployed.
Image/video validation needs explicit bounded decoder/prober dependencies; unavailable
validation means quarantine, not a client-MIME bypass.

## Ownership And Immutable Media

Every request derives customer/workspace/user from authenticated membership. Clients
cannot supply authoritative owner IDs or storage paths. All media, drafts, reviews,
publication plans and runs carry workspace ownership; joins use compound keys.
Connection/account selection must match workspace + integration + platform and bind
the current connection generation. Cross-workspace digest knowledge never grants
access or confirms asset existence; public/global digest lookup is prohibited.

Proposed shared immutable records (UUID-hex IDs; SHA-256 lowercase hex):

- `MediaObject`: workspace_id, media_id, original_sha256, immutable storage_locator,
  byte_length, validated_mime, width/height, optional duration_ms, validation_version,
  state (quarantined/ready/rejected/tombstoned), creator and timestamps.
- `MediaVariant`: workspace_id, variant_id, media_id, exact output_sha256,
  immutable storage_locator, dimensions/duration/codec metadata, processing_recipe
  version and fingerprint. A changed crop, transcode, trim, poster or source upload
  creates a new variant, never overwrites bytes referenced by approval.
- `MediaReference`: media_id + variant_id + output_sha256; resolved only within the
  authenticated workspace, ready state and current validation policy.

Initial engineering bounds: JPEG/PNG images up to 8 MiB, MP4 video up to 64 MiB,
stream chunks at most 1 MiB, at most 20 media references per draft and 64 KiB
canonical draft JSON. Proposed operational quotas are enforced by customer plan
before upload and by actual streamed bytes; no unlimited unknown-length uploads.
Pixel/duration/codec limits belong to the manifest and validator, and must pass
before state becomes ready. Provider-specific restrictions may be stricter.

`MediaStore.put_if_absent(scope, expected_digest, expected_size, bounded_stream)`
returns an opaque immutable locator and independently verified digest/size.
`open_exact(scope, locator, expected_digest)` streams only that immutable object.
`delete_unreferenced(scope, locator)` is a separate retention operation; it cannot
break approved/in-flight publication references. Locators are generated server-side,
not URL/path inputs. Local test storage rejects symlink traversal; cloud keys are
server-derived workspace/digest keys. Quarantine cleanup cannot race a finalize.

No server fetch of supplied media URLs. Upload bytes or select an owned library
asset. Landing-page URLs are declarative destinations: validate HTTPS, no credentials,
length and approved domain; never fetch them in B14. Provider-required temporary
asset serving, if later necessary, is generated from private owned storage with
bounded expiry/scope, never an arbitrary customer URL. This leaves no SSRF escape
through redirects, previews, thumbnails or remote transcode inputs.

## Draft, Review And Preview Interfaces

`CampaignDraftRevision` is append-only: draft_id, revision, workspace_id,
account_scope (existing AccountScope), connection_generation, capability_id/version,
mandate_id/revision, goal_id/revision, currency, timezone, content discriminated union,
media references, creator and created_at. Content contains the explicit fields
required by the audit; strings/lists use manifest limits and schema bounds.

Provider content unions are typed, not free-form arbitrary payloads. Google content
includes bounded supplied headlines/descriptions, landing-page/path text and reviewed
keyword match types; Meta/TikTok content includes supplied copy, CTA and selected
account-owned tracking/identity IDs. Audience selections use the supported manifest's
geography/language/platform-owned targeting identifiers and explicit exclusions.
No automatic CRM audience uploads or sensitive audience inference is introduced.
Budget is integer micros, explicit owner/type and fixed schedule, within the
approved mandate. Proposal aggressiveness never raises the mandate cap.

Shared service signatures for downstream teams:

1. `create_revision(scope, draft_id, expected_revision, typed_content) -> RevisionRef`
2. `validate_revision(scope, RevisionRef, capability_snapshot) -> ValidationReport`
3. `compile_preview(scope, RevisionRef) -> ReviewArtifact`
4. `approve_exact(scope, ReviewArtifact.digest, expected_revision) -> ApprovalRef`
5. `compile_publish_plan(scope, ApprovalRef) -> PublishPlanRef`

All mutation endpoints require current owner/admin role, session, CSRF and expected
revision. A metadata/display edit that does not affect publication can live outside
revision content; any actual publication-field, media-variant, mandate, account,
connection-generation or capability version change creates a new revision and
invalidates approval for the new head. Approval never follows a mutable pointer.

`ReviewArtifact` contains canonical publication fields + ordered exact media refs +
preview manifest + capability snapshot + ownership/mandate/goal bindings. Its digest
is SHA256(domain='inlet.campaign-review.v1' + canonical UTF-8 JSON). Canonicalization
is specified once: sorted object keys, fixed UTC timestamp form, integer micros,
no floats, NFC-normalized strings before validation/preview, preserved list order and no silent text
rewriting after approval. Pydantic serialization and compiler versions are pinned.
Store reviewed_by, session/audit reference, approved_at and exact digest. Changing
code/manifest rendering semantics invalidates the artifact rather than reinterpreting it.

Preview and publication are compiled from the same frozen normalized content, not
independent client/server mappings. The preview shows actual uploaded variant bytes,
copy, destination, targeting summary, tracking selection, currency/budget/schedule,
mandate binding and intended activation state. Responsive providers may choose among
approved supplied combinations; preview must show the complete allowed set and label
that variation, not promise pixel-identical rendering on every device. Provider
transcoding is distinct from silently choosing different creative content. A preview
that needs unavailable validation remains unapprovable.

## Declarative Publication Contract For B15/B16

`PublishPlan` binds plan_id/version, workspace/account/integration/generation,
ApprovalRef + review_digest, mandate_id/revision, capability version/API version,
validated exact media refs, precondition snapshot requirements, maximum exposure and
an immutable ordered operation DAG. Operations use typed kinds such as
upload_media/create_campaign_paused/create_group_paused/create_ad_paused/verify/
activate; stable local resource keys and dependency references replace guessed remote
IDs. There is no executable script, arbitrary HTTP method, endpoint or arbitrary
provider payload supplied by a customer.

A platform compiler owns the exact typed resource mapping; a shared coordinator owns
claims, reservations, fencing, cancellation and durable progress. Persist compiler
version and request-payload digests. Bridge to current `ActionDraft` with typed plan
ID/revision/review_digest/content_digest references and exposure bound; the bridge
must validate all fields agree, as in the existing Google operation binding repair.
A new campaign has no pre-existing campaign resource: use a namespaced plan key and
explicit account-level absence/preconditions, not a fabricated provider campaign ID.

Suggested adapter port:
- `validate(plan) -> QualifiedValidation` (no mutation)
- `observe(scope, plan, now) -> CurrentEvidence` (qualified read adapter)
- `prepare(step, dependencies) -> ExactRequestDigest` (no mutation)
- `dispatch(step, stable_request_key, fence) -> OperationReceipt`
- `reconcile(step, receipt_or_unknown, scope) -> ConfirmedResult|NoEffect|Unknown`

`OperationReceipt` records exact account scope, step key, request digest, any remote
resource IDs, attempted_at, transport outcome and verification status. Never store
raw secrets or entire provider response bodies in audit. Budget reservation is shared
with B07 and persists through uncertain outcomes; no parallel worker obtains a second
reservation for the same logical publication. Re-read entitlement, role/approval,
connection generation, mandate limits and fresh state at claim/dispatch/activation.
Stale required data stops the action. Plan edits require a new plan/action; old fenced
work cannot start later steps for the edited draft.

Create paused resources first. Activate only after every required dependency and
read-back result matches the exact approved plan, the customer approved activation,
and the spending mandate remains valid. Partial errors leave a durable graph of
created resources, keep remaining resources paused, and reconcile before retry.
Providers without safe idempotency/read reconciliation cannot be marked launch-ready;
resource-name coincidence is not proof. Timeout-after-creation remains unknown and
must not create a second campaign. Cleanup of paused partial resources is separately
scoped, audited and cannot pretend spent money was reversed. Changed account state
or mandate pauses stop activation even if media upload previously succeeded.

## Work Split And Acceptance Gates

Freeze these records/ports before parallel dependent work. B14 owns ownership,
immutable media validation/storage port, draft revisions, review artifact/compiler
contract and preview UI. B15 owns only Google manifest/compiler/provider mapping,
step receipts and reconciliation behind that port. B16 Meta and TikTok can work
independently after the same interface contract, with separate capability fixtures.
Shared coordinator/schema changes are serialized, not implemented independently in
each adapter. Existing live mutation boundary stays disabled throughout offline work.

Required tests before claiming B14: two-workspace asset/draft denial including known
foreign hashes; upload/hash/size/type/probe failures; immutable variants; concurrent
revision/approval conflict; every publication-affecting edit invalidates approval;
preview manifest equals compiled plan content; provider unsupported fields reject;
no remote URL fetch; grant/mandate/account changes block claim; deleted/quarantined
asset blocks activation; quota and stale-data checks; roles/CSRF and audit history.

B15/B16 additionally require mocked concurrent publish/retry, timeout-after-create,
partial DAG failure, no duplicate resources, exact read-back, cancellation between
steps, media-processing failures, reservation preservation and declined activation
when authorization/entitlement/evidence changes. Live end-to-end qualification is a
separate release gate; fixtures alone do not make a purchasable working integration.

## Decisions Versus Routine Engineering

Routine authorized choices: immutable revisions and domain-separated fingerprints;
strict typed discriminators; authenticated streaming uploads; no remote URL fetch;
local fake storage for tests; disabled factories; paused-first resource DAG; bounded
engineering upload/list/JSON caps with visible errors; exact ownership/CSRF checks.
Proceed with those without another approval.

Concrete owner decisions before live launch, not prerequisites for offline contracts:
confirm the proposed campaign matrix and initial budget/bidding variants; approve
private storage location/retention and commercial storage quotas/cost; confirm user
rights/consent text for supplied creative and any retention obligation after account
closure; approve the live provider permissions and spending authority separately.
Recommendation: narrow matrix above, private regional storage matching customer data
location, owner-supplied creative only, explicit publish review and paused-first
creation. Retention durations/quota pricing cannot be invented as contractual claims.
Media rights/licensing are customer attestations, not something a file parser can prove.

## Core Package Boundary (2026-10-06)

The first implementation's MediaStore, MediaRef, RevisionInput and ReviewArtifact ports
are frozen as core review interfaces in `app/campaign_review/contracts.py`. They do not
yet constitute the complete PublishPlan port proposed above. B15/B16 must wait for a
concrete reviewed compiler mapping. Missing tracking, account-owned conversion IDs,
bidding configuration and capability manifest block publication; adding any such
field requires a new customer-visible revision, preview digest and approval. Existing
offline approvals cannot authorize provider defaults filled in later. See
`inlet-campaign-review-core.md` for implemented behavior and remaining acceptance gaps.
