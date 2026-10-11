# Typed Planning Creative Basis V1

This follows the reviewed Q01/Q02 mechanical qualification. Q03/Q04 still need
substantive creative guidance and server-verified selected media. An image ID/hash
embedded in prose is not an owned-media witness. This interface prepares those
dependencies without enabling a policy or changing existing document bytes.

## First Package: Standalone Contracts Only

Add `app/planning_documents/creative_basis.py`, using the existing frozen, strict,
extra-forbidden document primitives. All values carry planning-only authority.

- `CustomerProductV1`: required bounded `name` (Title); optional `list_price`
  object with strict nonnegative integer micros (Amount) and Currency; bounded
  tuples `customer_asserted_facts` and `restrictions` (Text, at most20 each).
  Provenance is exactly `customer_supplied`; `claim_review` is exactly `required`.
  These are declared facts, not verified claims, rights or eligibility.
- `PlanningMediaSelectionV1`: exact media ID and expected SHA256 only. Never
  accept a client-supplied workspace, path, URL, MIME, dimensions or ownership.
- `CreativeInputV1`: optional product and tuple of up to30 media selections.
  Duplicate media IDs are rejected, including conflicting digests. Input order
  is explicit customer order; no normalization changes it silently.
- `OwnedPlanningImageV1`: server-only metadata witness: workspace ID, media ID,
  SHA256, size, MIME (`image/png` or `image/jpeg`), width, height, created_at,
  observed_at and nonnegative strict privacy revision. Reuse existing image byte
  and pixel limits:1..8MiB per image, strict positive integer dimensions with
  width*height<=16,000,000, and128MiB aggregate library size. Do not use the64MiB
  video limit. Require aware datetime/ISO timestamp inputs, reject numeric/bool
  timestamp coercion and normalize instants to UTC; created_at<=observed_at. These values
  describe integrity-checked owned bytes at observation time, never product
  depiction, suitability or rights. `visual_assessment` is `not_assessed`.
- `CreativeBasisV1`: workspace, goal currency, privacy revision, requested
  `CreativeInputV1` and ordered tuple of image witnesses. Revalidate all nested
  models. Require exact one-to-one ID/digest/order match; every witness matches
  workspace/privacy. Optional product price currency must equal goal currency.
  The sum of image byte sizes stays within the existing media-library bound.

Use explicit schema tags `inlet.customer-product.v1`,
`inlet.planning-media-selection.v1`, `inlet.creative-input.v1`,
`inlet.owned-planning-image.v1`, and `inlet.creative-basis.v1`. Canonical digest
uses the existing domain-separated document fingerprint. No authority is granted
by successfully parsing a witness: only the later authenticated reader creates it.

No current input/API/composer/policy/schema migration/storage/portal registration
in this first package. Tests cover malformed/coerced/extra values, duplicate and
foreign witnesses, digest/order/privacy mismatch, currency, byte/pixel bounds,
UTC/DST ordering, deterministic serialization and authority denial.

## Next Reader Boundary (Design Before Implementation)

Use existing private media storage and customer authority. Snapshot exact owned
rows under the original session and paid workspace access; release the SQL
transaction for bounded storage I/O; read/hash/decode only the selected images;
then recheck original session, membership, entitlement, privacy and every row in
one final SQL context before returning witnesses. No URLs or external requests.
Rows alone are insufficient. Missing, foreign or mismatched bytes/metadata fail
closed with bounded errors; no client-provided snapshot bypass is allowed.

Currentness and final plan persistence must bind the complete retained witness.
Immutable history validates stored evidence, while deletion/privacy prevents
resurrection. Those persistence/export/erasure contracts will be frozen separately
before connecting this standalone basis to a future canonical private policy.
Existing v1–v4 historical digests and default v3 behavior remain unchanged.

## Provider-Alone Fixture Seam

Separately allow the test-only `prepare_q16_basis` helper to accept an owned native
account factory, preserving its Google default and existing wrapper. Meta's factory
supplies two campaigns/ad sets with explicit partial coverage; TikTok's supplies
one regular-family campaign/ad group. Same confirmed Common Basis and owned image
upload; TikTok has no owned video. Reporting uses actual MockHTTP imports when
included. Social selected events remain unsupported, never Google-inferred.

## Creative And Human Qualification

Later Meta briefs must distinguish a selected available image from required
production/placement review. TikTok requires an explicit missing-video gap and
product introduction, demonstration and factual CTA production steps. Respect
exclusions, one-asset capacity, partial coverage and null native-budget proposals.
Metadata integrity never proves image suitability. Human expert usefulness and
visual assessment, hosted/live operations, merge and release remain separate gates.
