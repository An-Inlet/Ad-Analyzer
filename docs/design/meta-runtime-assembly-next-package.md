# Meta Creation And Separate Activation Assembly

Design-only successor to Google TLS `4ff8d74`; no runtime changes or new schema.
Google, Meta and TikTok remain the launch scope. This is the next bounded Meta
image slice, not a recommendation-only scope change or permission to enable live ads.

## Existing Callable Components And Missing Wiring

- `app/collectors/meta_catalog.py:MetaCatalogHTTP(context_reader, profiles,
  transport=..., clock=...)` reads actual v26 account/promote_pages/adspixels edges,
  bounds pagination and returns opaque `SocialCatalog` options. It deliberately
  returns native-configuration/conversion/audience/declaration qualification
  blockers. Discovery is not publication qualification.
- `app/publication/social_review_runtime.py:SocialReviewRuntime` carries environment,
  catalog, exact profiles, requirements by profile digest and clock. Its getter is
  still None. `app/api/customer_social_review.py` depends on that separate getter.
- `social_selection.resolve_selection` and `social_review_service` already persist
  exact configuration and explicit customer declarations. `SocialRequirements`
  accepts only verified no-DSA rules. Applicable/unsure or personal-DSA capture is
  unsupported; do not turn an operator profile boolean into the customer's answer.
- `social_execution_intents.prepare_plan` refreshes catalog, reloads the exact owned
  confirmed configuration, constructs a request-local declaration reader through
  `social_review_service.meta_declaration`, then calls `SocialPlanProducer.produce`.
  Reuse this path; assembly must never construct an unconditional declaration reader.
- `MetaPublicationTransport` and `MetaActivationHTTP` already implement actual
  reviewed image upload/paused graph/status-only activation/readback. Existing
  coordinator preserves separate approvals, receipts and the original parent hold.
- `MetaConnection` stores owned integration/account, generation and encrypted
  credentials. `app.meta.service.ConnectionService.access_token` opens
  `Vault(settings).open(workspace_id, external_account_id, encrypted_credentials)`
  and requires token expiry beyond five minutes. No silent token renewal is needed
  or authorized for this slice; expiry requires reconnect.
- `ScopedProviderMediaReader` verifies exact DB-owned media against private bytes.
  Use short original-session-bound private sessions around media reads rather than
  reusing a request session whose transaction the coordinator has released.
- `customer_execution_runtime.get_configured_customer_execution_runtime` currently
  rejects all social paths; `CustomerExecutionRuntime` otherwise carries generic
  CreationRuntime/ActivationRuntime but Google-specific catalog fields. Add Meta
  composition without forcing social catalog data into those Google fields.

## Minimal New Frozen Ports

Proposed additive `app/production_runtime/meta_contracts.py`, preserving every
existing Google manifest, plan and configuration digest:

```
MetaExecutionManifestV1:
  schema_version = 'inlet.meta-execution-manifest.v1'
  manifest_id, revision
  environment: contract_test | live
  api_version = 'v26.0'
  evidence_source_id, evidence_profile_digest
  configuration_bundle_digest
  live_execution_enabled: required strict bool
  activation_enabled: required strict bool
  credential_minimum_remaining_seconds: required int >= 300
  context_lifetime_seconds: required int > 0, <= credential minimum, <= 300

MetaConfigurationBundleV1:
  schema_version = 'inlet.meta-configuration-bundle.v1'
  profiles: bounded nonempty tuple[MetaConfigurationProfile] (<=10)
  requirements: bounded tuple[SocialRequirements]
  # Unique profile digests; exact one-to-one rules; no extra/missing keys.
  # Required profile numbers and wording remain explicit; no inferred defaults.

MetaEvidenceDescriptor:
  source_id, profile_digest, environment
  kind: contract_scenario | qualified_live_source

MetaExecutionEvidence (server dataclass, never JSON):
  descriptor: MetaEvidenceDescriptor
  configuration: QualificationReader
  creation: ExposureReader
  activation: ActivationExposureReader

RegisteredMetaEvidenceSource (server dataclass):
  descriptor
  build(sessions, authorize, actor_id, clock) -> MetaExecutionEvidence

MetaOwnedContexts (request-owned context manager):
  catalog(SocialCatalogRequest, now) -> MetaCatalogContext
  publication(SocialBoundRequest) -> SocialProviderContext
  activation(ActivationRequest) -> ActivationContext

configured_meta_execution(db, principal, provider, settings, media_store, *, clock)
  -> context manager of optional Meta bundle
```

`QualificationReader`, `ExposureReader` and
`ActivationExposureReader` are existing coordinator ports, not new economic proof
formats. Configuration proof must bind the exact social plan/account/v26/time and
keep unresolved facts unresolved. Source descriptor is never proof. These are the existing callable aliases; no alternate proof schema is introduced.

Manifest and configuration bundle are bounded duplicate-key-rejecting server files
pinned by separate path+digest settings. Neither accepts tokens, proof objects,
import strings, executable callbacks or native resource IDs from customers. Source
registration remains explicit trusted Python construction; no shipped live entry.
A pure descriptor gate precedes source construction, credential reads and HTTP.
The shipped real Meta transport requires a live enabled manifest and refuses every
contract-test manifest before HTTPTransport construction. Tests explicitly inject
MockTransport at that one low-level seam. Constructors open no sockets; no retries.

The bundle does not add an arbitrary currency-exponent override: initial supported
currency mapping must be verified in code and profile/native account must agree.
Reuse an already verified supported mapping if present; otherwise initially USD=2
with truthful unsupported results for other currencies. No legacy profile digests
are changed or upgraded in place.

## Owned Context And Composition Boundaries

1. Bind actual `db.get_bind()`, original actor/session authorizer and configured
   identity provider per request. No global principal/session engine.
2. In a short private transaction, lock canonical workspace→user→session→membership,
   validate `execution_mandates.current_account`, then read current Meta generation,
   owned integration/account/status and vault ciphertext. Check credentials and
   min remaining lifetime; close the transaction before provider/storage IO.
3. After IO, reauthorize the original session and exact generation/ciphertext before
   admitting results. Close all credential contexts/transports on every exit.
   No assumption that holding a token makes an expired/revoked session current.
4. Media access uses the same original-session fence and exact reviewed binding;
   private storage reads cannot supply foreign or changed media. Provider graph
   publication still uses existing source-current/configuration-current final gates.
5. New composition selects by the existing typed plan/request provider. Google
   qualifier/catalog/context continue unchanged; Meta receives only Meta paths;
   TikTok remains unavailable before evidence or credential IO. Generic run/receipt/
   activation routes dispatch using stored typed original requests, not URL guessing.
6. Request-local ExitStack owns lazily constructed admitted provider bundles. A
   provider factory is invoked only when that provider's typed operation is selected;
   metadata capability discovery does not call an evidence reader. Preserve explicit
   legacy injected runtime behavior. Existing Google-only deployment stays identical.
7. `CustomerExecutionRuntime` has one environment: when both manifests are present,
   require exact environment agreement before composing; mismatch is unavailable,
   never silently promote one provider. A missing Meta manifest/source does not
   disable an otherwise valid Google bundle. Capability provider availability is
   explicit and reflects admitted bundles, not inert adapter slots or settings alone.
8. Social-review API receives an additive configured dependency using this same
   frozen Meta profile/rules/context bundle; do not override the getter in acceptance.
   Exact requirements/profile changes invalidate forward configuration use through
   existing checks. No global hot-reload/revocation claim; process pinning remains
   a coherent deployment/draining responsibility.

## Qualification Blocker Must Stay Visible

MetaCatalogHTTP currently emits four unconditional qualification blockers. It is
incorrect to erase them just because a trusted source ID exists or local serializer
validation passed. This package can prove an actual configured **contract-test**
journey while retaining those flags; `social_execution_intents` already denies live
plans with catalog blockers. A real live-qualification follow-up needs an exact
current catalog/plan qualification result that accounts separately for conversion
eligibility, reviewed audience mapping and declaration rules. Any mechanism to
resolve catalog blockers requires its own reviewed typed evidence interface, not
an unreviewed list filter in this assembly package.

Required owner/deployment inputs: approved explicit attribution/age/locale/currency
profiles and exact declaration wording/rules; controlled manifest rollout; a real
qualified configuration/economic evidence source satisfying existing contracts.
Provider/native evidence must establish supported exact field combinations and
current conversion eligibility. No profile choice, token, native lifetime budget
or owner approval alone proves unreported exposure/headroom or prevents outside
writers. Preserve full existing PortfolioExposureReader and retained-hold gates.
These are evidence/policy prerequisites, not excuses to skip offline context,
factory, API or customer-flow engineering. TikTok's unverified native catalog
parser remains separate and cannot be enabled through this Meta source.

## Bounded Implementation And Acceptance After Approval

New Meta contracts/configuration/owned contexts/assembly modules plus minimal
provider-composition and social-review dependency changes; no migration. Preserve
Google v1 bytes/hashes, Google configured TLS acceptance and default-disabled
capabilities. Do not add unused generalized optimization/worker registry ports.

Actual no-getter-override API and TLS acceptance on both DBs:
- Start with current owned Meta connection and real B14 approved image/media input;
  no seeded execution review, attempt, receipt or reservation.
- Actual injected Meta catalog HTTP → opaque option → separate explicit declaration
  configuration review/confirmation → production mandate consent → exact creation
  review/approval → actual uploaded image and paused graph → separate activation
  review/approval/status requests → exact readback/receipt and one retained hold.
- Financial/configuration source fixtures are explicitly contract-test server
  readers, not client proof. Assert real transport + fixture source denies before IO.
- Missing manifest/source/rules, wrong provider/environment, expired credentials,
  original-session revocation during IO, reconnect/generation drift, privacy/media
  deletion and changed declarations all deny without publication.
- Unknown creation/activation never replays; reconcile only original IDs, duplicate
  receipts retain one hold, cancellation/revocation fences future emission. Apply
  Google activation read-phase regression to private Meta contexts as well.
- Coexistence Google+Meta capability/dispatch tests and malicious direct TikTok body
  fail before factory/credential/network activity; transport/context cleanup on errors.

No live qualification or provider verification is claimed by this proposed package.

## Frozen First Checkpoint

`app/production_runtime/meta_contracts.py` now defines the manifest, pure
`admit_meta_source`, server-only evidence dataclasses/factory and owned-context
protocol signatures above. `meta_configuration.load_meta_execution_configuration`
accepts `(manifest_path, expected_manifest_digest, bundle_path)` and returns optional
`(MetaExecutionManifestV1, MetaConfigurationBundleV1)`. The manifest itself pins
`configuration_bundle_digest`; a redundant separately configurable bundle digest
is unnecessary. All three absent means unavailable; partial settings fail closed.

The bundle owns canonical immutable bytes. `from_document(object)` validates
profiles and rules; `.profiles` and `.requirements` return fresh typed defensive
copies, `.digest()` commits the exact validated document. This avoids pretending
existing mutable social nested lists/maps become immutable inside a frozen outer
model. Exact one-to-one rules, explicit wording, no-DSA and USD exponent2 are required.
Existing social profile hashing is reused unchanged.

`meta_transport.meta_execution_transport(manifest)` is the explicit low-level real
HTTP seam. It rejects contract-test and disabled-live before constructing transport.
There is no registration or API wiring in this checkpoint. This guard does not by
itself qualify live use: all catalog blockers and existing financial gates remain.
