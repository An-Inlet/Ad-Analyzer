# Private V5 Common Basis Artifact Qualification V1

Design-only interface, based on `4100fe5717eb55c298a1ddc79f7661e3348b1a6f`.
Implementation follows review and the root's frozen genuine-v5 API test package.
No production change, policy-default switch, new source permission, browser claim,
expert score or live qualification is authorized by this document.

## Existing evidence and invariant basis

Preserve `comprehensive-planning-quality-cases.md`, the Q01/Q02 review packet,
`tests/selected_q01_q02_fixture.py`, `tests/social_common_basis_fixture.py`, and
all original artifact bytes/digests. Their v3/v4 limitations are historical facts,
not failures to erase by replacing outputs. New results are a separate packet.

Each new journey uses the original authenticated owner/session throughout upload,
source acquisition, saved input, generation, read and export, with one exact owned
native account. Never replace ownership with a callback or copy an old proof into
a new session. Independent test runs necessarily have different generated IDs;
comparability means identical declared basis and provider topology, not pretending
those independently created databases share identifiers.

The frozen basis remains USD, America/New_York, September 2026 reporting,
August comparison, November goal/budget, confirmed $12,000 merchandise-net-sales
goal and $8,000 complete Shopify baseline, $1,000 November ceiling, balanced
aggressiveness, reusable travel mug at $25, one selected owned image and creative
capacity one. No approved health claims/testimonials, and no owned TikTok video.
Reporting dates do not become the budget period. Preserve all other existing
constraints, exclusions and scenarios exactly. Use the existing synthetic PNG;
byte decoding/metadata does not establish visual suitability, rights or ad approval.

## Minimal test-only seams and ownership

1. Extend `prepare_q16_basis` with optional keyword
   `owned_image_upload: Callable[[int], tuple[str, str]] | None = None`, returning
   `(media_id, sha256)`. Forward this optional argument through the two existing
   Common Basis helpers; defaults and `prepare_q16_case` remain unchanged.
   The callback receives the newly owned workspace ID and closes over the actual
   original HTTP client and trusted LocalMediaStore. Invoke it outside SQL after
   existing goal/native/paid preparation and before constructing the input body.
   It performs POST `/api/customer/v1/workspaces/{workspace_id}/media` with PNG
   bytes and the actual session/CSRF headers, checks the real response, and returns
   only its ID/hash. It must not construct a MediaAsset row or return invented data.
   Keep the default direct-service upload and all November Q16 clocks unchanged;
   the new callback is used only by the October-stage qualification.
2. New `tests/creative_common_basis_fixture.py` provides
   `prepare_creative_common_basis(engine, config, replicas, patch, artifacts, *,
   platform: Literal['google_ads', 'meta_ads', 'tiktok_ads'],
   selected_value: Literal['10', '0'] | None = None)`.
   It returns a small fixture record containing the existing Q16Basis, saved-input
   request body and native-call log, without serializing authentication material.
   Google delegates to the existing real range/event/selection/capture helper;
   social delegates to its existing owned native-account factory. Social rejects
   non-None selected_value, rather than interpreting Google observations as social
   metrics. The Google None variant is explicitly missing, not a default success.
3. The test application includes the actual media and planning routers. Its media
   dependency and explicitly private canonical-v5 PlanningDocumentService share
   one trusted LocalMediaStore. Retain the normal service-factory principal
   snapshot/rollback behavior; configure only canonical policy and store. Do not
   replace readers, composers, evidence, retained dispatch or repository callbacks.
   Override the old helpers' v4 constructor configuration only for this new path.
4. New `tests/test_creative_common_basis.py` owns actual API assertions/artifacts.
   Do not edit product modules or existing expected document hashes. Reuse the
   root's frozen actual-v5 API qualification patterns after its commit, not WIP.

The new input adds `inputs.creative` with CustomerProductV1 name
`Reusable travel mug`, list_price `{micros: 25000000, currency: 'USD'}`,
empty customer_asserted_facts, restriction
`No approved health claims or testimonials.`, and exactly one media selection
`{media_id: actual_upload_id, expected_sha256: actual_upload_sha256}`.
Keep the existing product_offer prose and actual matching image references. Do not
infer material, insulation, durability, performance or other product features.

## Genuine API and proof acceptance

Use actual input-save/create, generation, owned read and export endpoints with
ordinary idempotency keys. Assert the saved immutable typed input, original account,
goal revision and selected capture IDs match the requests. The generated document
must be genuine canonical v5, with its complete reporting/traffic/commerce and
creative dependencies persisted atomically by the service. Inspect those stored
relationships; never insert a version, witness, receipt or private collection to
make the assertion pass. A repeated identical generation request returns the same
saved version/document/proof observations, not a newly stamped image observation.

Google positive retains September 100 clicks, 10 selected conversions and $100
reported spend, plus explicitly observed August zero selected conversions. The
true-zero variant changes only the selected September value to zero. Missing
selected rows remain unknown (including comparison where the fixture omits it),
never zero. Preserve exact campaign and observed-adgroup locations without assigning
campaign metrics to the child. Explicit chosen capture IDs must survive saved input
and proof binding. No conversion-family or native-budget authority is invented.

Meta preserves two campaigns and observed adsets with explicit partial catalogue
coverage; TikTok preserves one regular campaign and observed adgroup. Both use
explicit empty selected_reporting, retain unsupported selected-reporting gaps and
any actual reporting gaps, and must not acquire fabricated Google statistics.
The new output must contain scoped product-specific creative production, the
selected owned-image commitment with `visual_assessment='not_assessed'`, and
production-required status. TikTok's three-shot storyboard/caption/edit/review
instructions explicitly require production of video; an image is not an owned
video, Spark identity or authorization. Assert capacity one across all output,
exact image order and product price, restrictions, and absence of unsupported
native budget or delivery/causal claims. Metadata ownership is not copyright or
commercial-music approval. These cases do not establish every frozen Q03/Q04 input
statistic merely by providing useful creative instructions.

Assert no provider mutation, execution run, approval or reservation is created by
these read/planning journeys. Paid synthetic fixture setup is not live entitlement
or financial execution qualification. Existing adversarial v5 tests remain the
source of broader session/privacy/currentness claims; do not count this positive
packet as all those tests or as full Q11/Q16 closure.

## Artifacts, validation and remaining boundaries

Write actual generated document and exact owned export JSON after assertions to
per-case/per-database tmp_path; retain them under a new
`/workspace/inlet-evidence/20261011/creative-common-basis/artifacts` directory.
A manifest records file SHA256, actual document digest, canonical policy/generator,
case/value/database identity, source commit, commands, JUnit evidence and declared
fixture boundaries. Never overwrite the prior selected/social packets. Do not
include cookies, CSRF values, sessions, tokens, storage paths, encrypted grants or
private collection envelopes. Preserve initial failed evidence and mark incomplete
cases honestly; no expected-artifact substitution.

After implementation approval, run bounded SQLite gates, then coordinated
PostgreSQL cases; preserve Q16 wrapper and old selected/social Common Basis tests.
Run whole Ruff and configured mypy before the code freeze. No tests or database
work are part of this design commit. Actual authenticated archive qualification is
separate from the ordinary owned JSON export unless explicitly included and tested.

The deliverable is reproducible synthetic actual-API output available for a later
human review. Q01–Q16 remain partially qualified. No expert quality score, browser
journey, visual suitability, provider live availability or production-v5 default
is inferred. Real storage deployment and customer UI exposure remain independent
assembly decisions; this package changes neither.
