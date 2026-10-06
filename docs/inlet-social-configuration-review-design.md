# Durable Social Declarations And Exact Cover Review

Implementation note: initial0059 is explicitly limited to no-DSA Meta answers and
TikTok pair reviews. The full personal-declaration design below is NOT implemented
or enabled. See inlet-social-declaration-privacy-lineage.md for the closure-safe
privacy dependency. Current storage/service does not expose customer routes or
connect approval references to execution; those are subsequent integration steps.

Design only. Inspected PR166bc5befb and customer journey PR1659ac2bb. No schema,
code, runtime enablement, provider request or policy expansion is proposed before
interface agreement and a migration reservation. Spending/rebudget work takes
priority; this package supplies review evidence, never spending qualification.

## Concrete Gaps In Current Ports

`MetaDeclarationReader(request, now)` currently returns request_digest,
audit_record_id, confirmed_by/at and explicit no-special-category plus DSA values.
The producer verifies source request and time and required DSA values. However:

- SocialCatalogRequest binds owned account/generation/source/audience, but not the
  chosen catalog option, server profile or the version of declaration wording.
  The same request could therefore select a different profile with different DSA
  requirements while reusing a declaration unless the reader adds that binding.
- The emitted SocialPublicationReview binds declaration values in configuration;
  it does not bind the immutable record proving who actually confirmed those values.
- The producer does not currently prove the declaring actor still owns the source
  workspace. An arbitrary callable supplied by internal code could return a nominal
  audit ID without a real record. The customer facade must use an owned DB reader.
- TikTok cover is an extra owned media ID outside the original B14 video artifact.
  The producer correctly reads/revalidates it into a full ProviderMediaBinding and
  compiles it into the plan. It still needs a customer view and immutable approval
  proving that exact cover/video pair was reviewed before execution review approval.

None of these facts licenses removing catalog/native qualification blockers.
TikTok's native parser blocker stays present. Meta discovery is not spend/cap or
jurisdiction qualification.

## Proposed Shared Typed Boundary

Add `SocialConfigurationSelection` (server-built, frozen):

- schema `inlet.social-configuration-selection.v1`;
- exact SocialCatalogRequest and request_digest;
- opaque option_id, profile_digest, and profile requirements digest;
- platform and server-selected environment (`contract_test` or `live`);
- requirements version and immutable requirements description digest;
- Meta: declaration wording/version, required declaration fields and DSA-required
  state from the selected server profile; no customer-derived requirement flags;
- TikTok: primary video ProviderMediaBinding and selected cover ProviderMediaBinding,
  including owner-resolved IDs, SHA256, byte size, MIME/dimensions, decoder version
  and validation digest. No remote cover URL or customer-provided binding accepted.

Selection digest excludes catalog refresh timestamps so unchanged discovery can be
revalidated without needless consent churn, but includes the request, exact option,
profile/requirements and media bindings. Catalog freshness is separately checked on
prepare, confirmation and execution preparation. A label change is already part
of PR166 option identity and therefore requires refresh/review.

Add `SocialConfigurationReviewV1`, a strict discriminated payload:

- common selection, schema/version, source and scope, displayable supported profile;
- Meta: `special_category_answer` = `none_applicable | applicable | unsure`, explicit
  DSA beneficiary/payor entries only when prompted, and server-generated blockers;
- TikTok: exact video/cover bindings and the rendered-review acknowledgement wording;
- no free-form provider evidence, cookies, session token, raw provider response,
  executable payload, customer audience data or arbitrary metadata.

Only a confirmed `none_applicable` answer can produce the current Meta profile.
Applicable/unsure are truthful blocked review outcomes, not converted to empty
special_ad_categories. Do not precheck the answer. This is the customer's statement,
not Inlet's inference that the business legally belongs to a category.

Names are bounded normalized plain text (up to the existing200-character contract),
reject controls/blank required fields, render literally, and are never guessed from
account name, Shopify shop, user email or connected Page. When the selected profile
requires both names, explicit entries are required; otherwise do not fabricate
values. A change to names or requirement version produces a new immutable review.

## Durable Records And Migration Reservation

Recommend two new workspace-owned tables and one nullable existing-table link.
Root reserved revision0059 with down_revision0057, independent of replacement
audit0058. Root owns eventual merge0060. No migration is created by this proposal.

1. `customer_social_configuration_reviews`:
   id, workspace_id, account_id, integration_id, draft_id, source_revision,
   platform, environment, request_digest, option_id, profile_digest,
   requirements_digest, selection_digest, review_digest, typed review JSON,
   cover_media_id(nullable), created_by, created_at.
   Unique(id,workspace_id), composite owned account/integration FK, composite
   owned source-revision FK, and explicit owned cover FK when present. JSON is
   capped at64KiB. Immutable rows, no editable confirmed payload.
2. `customer_social_configuration_approvals`:
   review_id, workspace_id, review_digest, approval_digest, actor, confirmed_at.
   One immutable confirmation per review; repeat exact confirmation is idempotent.
   Composite review/workspace FK and actor FK. No session-token/hash storage.
3. Nullable `ProviderExecutionReview.social_configuration_review_id`, with
   composite workspace FK, only for social customer execution reviews. It is
   null on existing history. This is an audit link, not a shortcut around source,
   qualification, policy, ledger or exact execution approval.

The cover FK needs Unique(id,workspace_id) on existing MediaObject because its
current uniqueness is only global id and workspace+SHA. Add that constraint in the
same migration if relational cover ownership is selected. Do not use a bare media
ID FK and rely solely on later application filtering.

The nonpersonal approval envelope is protected audit evidence; the declaration
payload is explicitly privacy-erasable. Immutable means no in-place answer editing,
not exemption from authorized erasure. Add payload_state (available|erased),
erased_at and nullable typed payload. Erasure clears personal declarations and
payload-derived digests, prevents all forward use, and preserves only a minimal
nonpersonal tombstone with the existing audit identifiers. Exact personal-field
copies in downstream ProviderExecutionReview/plan storage must be inventoried and
redacted or deleted under the same authorized privacy transaction; a local-only
clear that leaves those copies is insufficient. No foreign-key RESTRICT may prevent
that privacy operation. Actor identifiers follow the established identity-erasure
policy rather than introducing a second identity-retention rule.

These are not commerce-derived order aggregates: erasure must target actual
declaration/identity dependencies, not indiscriminately delete unrelated advertising
consent for every Shopify order event. No new retention duration or closure purge
exception is introduced. Exact propagation hooks and permitted minimal tombstone
fields require lifecycle-owner agreement before schema implementation.

## Plan/Approval Binding Without Breaking Existing History

Add optional `configuration_review` to SocialPublicationReview with a strict
`SocialConfigurationApprovalRef(review_id,review_digest,approval_digest)` type.
Serialize it only when present, preserving exact historical v1 hashes when absent
(the existing Google optional-proof compatibility pattern). Present references
participate in the canonical plan/review digests. This is a deliberate reviewed
schema extension, not arbitrary extra JSON accepted from callers.

For the customer facade, the reference is mandatory for both contract-test and
future live social paths. For a future live runtime, all social dispatch admission
must require and revalidate it, regardless of calling facade. Existing internal
legacy contract fixtures may continue without a reference; that compatibility must
not become a public or live bypass. No global live factory is enabled here.

Extend the Meta declaration request to include this exact confirmed review binding,
option/profile/requirements digests. Prefer a new `OwnedMetaDeclarationReader`
server callable rather than silently widening the old reader's meaning:

`read_meta_declaration(db, wid, review_id, expected_digest, actor, now)
 -> MetaDeclaration`.

It reloads the immutable owned payload and approval, recomputes hashes, verifies
exact source/generation/selection/profile, confirms the persisted approval and current source remain valid and
checks the original confirmer's current owner membership. The caller is also
currently authorized through the existing session-bound ExecutionAuthorizer.
Returns only actual stored confirmed values. Use an adapter into PR166 producer
for this exact call; do not scan for an arbitrary latest declaration by request.

Producer accepts the server-selected confirmation reference and validated reader,
then embeds the reference into the canonical plan. Coordinator rechecks reference,
current source/media, exact confirmation and current actor before approval, claim
and final emission. Reconnect, source edit, profile/rule change, cover replacement,
confirmation actor role loss or deletion invalidates forward use. An unchanged
catalog refresh does not invalidate an otherwise exact confirmation by timestamp
alone. Provider evidence itself must still be fresh.

## Customer API And UI

Extend the execution intent union with discriminated social choices; do not force
Google-only fields into Meta/TikTok bodies.

- POST `/execution/social-configuration-reviews`: current approved draft ID/revision,
  opaque option ID; Meta explicit answers/names or TikTok owned cover_media_id.
  The server resolves all scope, media and profile fields, persists the immutable
  preview and returns readable exact values, blockers and digest.
- GET `/execution/social-configuration-reviews/{id}`: owner/session reauthorization,
  exact readable review and current/stale status. Stale review remains historical,
  not an executable configuration.
- POST `.../{id}/confirmation`: expected review digest and explicit acknowledgement.
  The server rechecks exact current source/selection/media/requirements and owner
  session after any IO/lock wait, then records confirmation. Blocked reviews may
  be displayed/saved, but cannot be confirmed for execution.
- POST `/execution/creation-reviews`: social variant supplies only confirmed
  configuration review ID/digest and separately consented mandate ID/revision.
  All declaration proof, media hashes, request and plan assembly stay server-owned.

Meta UI shows the actual campaign, audience, Page/purchase-measurement names and
supported profile before the declaration question. “Applies” and “Not Sure” show a
clear unsupported/review-needed state. Beneficiary and payer are separately labeled;
no default assertion or copied brand name. Explain exactly what is being recorded
and may be sent to the provider; do not characterize it as legal certification.

TikTok UI shows the exact source video and selected cover side by side, with real
private-media preview via authenticated bounded blobs. Server validates bytes;
video requires loadeddata/error handling and cover image decode, not metadata-only
success. Customer must review the actual pair. Changing the cover clears the local
acknowledgement and requires a new persisted config review. The original video
creative approval remains unchanged; the later configuration approval covers the
extra cover explicitly. Confirmation does not remove TikTok native-catalog or
configuration/spending qualification blockers or publish anything.

## Privacy And Export Classification

Send exact model/scalar columns and `SocialConfigurationReviewV1` serializer to the
export/lifecycle owner before first integrated tests. TABLES classifies both records
as workspace-scoped approval evidence with erasable personal payloads; scalar
fields are allowlisted. Export available payloads through the discriminated schema;
erased records export only their strict minimal tombstone, never stale digests or
reconstructed names. Erasure bumps the existing workspace export privacy revision
atomically and invalidates in-progress delivery through existing fresh fences.
JSON must use the strict typed serializer with matching source/owner/selection
bindings, no generic dump. Names are customer-supplied disclosure data, not harmless
technical metadata; avoid them in logs/errors/attention summaries. Existing archive
owner authorization, workspace privacy revision and delivery fences still apply.

Keep unconfirmed web form values transient until explicit Save Review. Do not retain
abandoned form contents in localStorage, analytics, telemetry or an extra event log.
Store neither image/video bytes nor extra full copies of source creative in this
new payload: retain exact owned media references/bindings and selected declaration
facts. Existing execution review already retains the canonical declared configuration.

Root explicitly requires privacy erasure/minimization of personal declarations.
This is a design constraint, not an unresolved request for a retention exception.
Before implementing, agree lifecycle hooks for every downstream canonical plan copy
and ensure erasure does not reinterpret a redacted historical hash as current proof.
If the established policy cannot specify a required residual field, omit it from
the tombstone or keep the affected confirmation path unavailable; do not create an
indefinite personal-data retention exception.

## Decisions: Routine Versus Owner Policy

Routine engineering, already authorized: immutable exact review+confirmation,
workspace composite FKs, server-resolved options/media, explicit answers, no defaults,
current ownership/session fences, actor/time audit, safe display, missing-evidence
blockers, backward-compatible hash treatment, strict export and disposable tests.
Root coordination: reserve migration; agree exact shared producer/ref signature;
assign shared coordinator/models and lifecycle/export edits to avoid collisions.

Genuine owner policy choices only if needed:

1. Expanding launch support beyond the existing no-special-category Meta profile.
   Recommendation: do not expand in this package; block applicable/unsure cases.
2. Only if a business requirement demands retaining personal declarations despite
   the approved erasure/minimization rule, that exception would require an owner
   decision. Recommendation: request no exception; implement erasable payloads and
   minimal nonpersonal tombstones under the existing policy.
3. Whether to support additional TikTok identity/cover formats beyond current
   typed single-video+image contract. Recommendation: keep current constrained
   contract and native parser blocker; broader support is a later scoped package.

Determining when provider rules require DSA fields is not an arbitrary owner choice.
The configured requirement profile must have a reviewed provider-rule basis; missing
or unverified applicability stays blocked. The owner supplies factual business
answers, not fabricated regulatory applicability proof.

## Acceptance Evidence

Both databases: no declaration by omission, blank required names rejected,
applicable/unsure blocked, source/profile/option changes invalidate, stale/cross-owner
confirmation cannot dispatch, exact replay idempotent, current confirmer role loss
blocks, session revoked during storage/provider IO prevents forward authority.

Actual image/video bytes and HTTPS browser: select owned cover, render exact pair,
change cover requires new review, cross-workspace media and corrupted bytes rejected,
no invisible default cover, decode-error prevents acknowledgement, logout clears
private previews/revokes blob URLs. Existing source video review is not rewritten.

Disposable PostgreSQL: populated predecessor→newhead→predecessor→newhead,
workspace/account/source/media composite FK denial, session/closure/source-update
races, protected lifecycle inventory and strict export serializer tests. No live
provider request, runtime enablement, production data or spending authorization.
