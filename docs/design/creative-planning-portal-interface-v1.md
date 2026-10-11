# Private V5 Planning Portal — Proposed Interface

Status: approved interface; bounded implementation is recorded in
[the package ledger](../inlet-creative-planning-portal-package-20261011.md).
No production activation. The current-state section below records the original gap.
Independent branch based on reviewed private v5 service/reuse and actual API fixture.
Default policy remains v3. Owner-managed Squarespace/public webpage is out of scope.

## Current State — Specific Missing Engineering

`app/portal/static/planning.mjs::editor` reads the server capabilities and delegates
to `plan-selected-captures.mjs`. That component accepts only canonical pairs v1–v4,
with selected reporting true only for v4. A correctly configured v5 response is
therefore rejected. `planning.mjs::inputIntent` never sends `creative`; the current
"Maximum Creative Concepts" input is only maximum_creative_assets, not a product or
owned-media selector. Thus the genuine v5 service cannot be used through the current
portal to create/edit/generate its inputs. This is code work, not a credential gate.

Existing server capability schema already describes v5 truthfully via the exact
policy/generator pair and selected_reporting_available=true. No extra capability
field or new backend architecture is needed. PlanningDocumentService defaults to
v3 and requires an explicit MediaStore for private v5; no browser toggle changes
server configuration. Existing create/revise/generate/current/version/export and
request recovery APIs already support actual v5, including exact retained creative
proof, original observations, currentness and immutable historical replay.

`plan-document.mjs` already renders generic actions, briefs, evidence, freshness and
planning-only notices, but does not separately display the typed product/image
basis. Existing JSON version export preserves the full server artifact. Extending
its v5 basis display is useful; it must not relabel saved evidence as a fresh read.

Existing workspace media APIs (`app/api/customer_campaign_review.py`) provide:

- GET /api/customer/v1/workspaces/{wid}/media: up to100 metadata rows, ordered by
  created_at/id. It is a bounded list, not a complete/paginated library promise.
- POST same route: raw bytes, CSRF and current scoped owner/admin checks, returns
  media_id,sha256,mime,width,height,size. Server storage may truthfully be unavailable.
- GET .../media/{id}: authenticated same-origin private bytes, no-store/nosniff.

The general API also supports video, but this creative basis accepts images only.
Reuse these APIs with image-only UI bounds; do not repurpose64MiB video preview
limits in execution-media.mjs. Media accessibility means workspace access, not a
copyright/right-of-use determination.

## Smallest Shared UI Contract

Add a pure `plan-capability.mjs` classifier shared by selected and creative controls:

    planningCapability(value, workspaceId) -> {selected: boolean, creative: boolean}

Validate schema v1, exact workspace, no-authority fields, strict boolean availability,
and exact canonical policy/generator pair. V1–v3 require selected=false; v4/v5 require
selected=true; creative=true only for the exact v5 pair. Unknown/mixed pairs reject.
This is UI classification, never server authority. Existing capability responses and
v1–v4 request shapes remain byte-equivalent; do not add creative:null to them.

Add `plan-creative-inputs.mjs` with a bounded DOM-only component:

    renderCreativeInputs(host, {
        capability, workspaceId, saved, library,
        uploadImage, readImage, current
    }) -> {readIntent(), clear()}
    clearCreativeInputs(host) -> void

`library` is the actual guarded same-workspace metadata response. Async upload/read
callbacks are supplied by planning.mjs and perform the current original-cookie,
epoch, session, CSRF and workspace checks before and after every wait. The component
cannot select arbitrary workspace/native IDs or invoke external URLs. It uses only
textContent/createElement, not HTML interpolation. Clear invalidates pending work,
aborts reads and revokes object URLs. No localStorage/sessionStorage/console payloads.

For legacy capability: no media fetch, store configuration, upload/preview or creative
controls; readIntent returns undefined. For exact v5: explicit CreativeInputV1 is
always returned, including deliberate `{product:null,media_selections:[]}`. Selected
reporting remains explicit too; empty is deliberate absence, not zero conversions.

## Editable Fields And Exact Serialization

Keep product_offer, global constraints and creative capacity as separate existing
fields. Do not silently copy between those and structured creative fields.

- Optional "Include Product Details" choice. Unchecked =>product:null. Checked
  requires name,1–160 characters. No inferred product/Shopify match.
- Optional list price. Blank =>list_price:null. Present =>micros integer0..10^15,
  currency exactly three uppercase letters. Parse a nonnegative decimal string with
  at most six fractional digits using integer/BigInt arithmetic, never float
  multiplication. Confirmed goal currency may be visibly prefilled/editable; no
  default amount, FX conversion or claim that retail price equals conversion value.
- Customer-Asserted Facts and Restrictions: ordered lines, at most20 each, each
  nonempty and at most2,000 characters. Label them customer-supplied and review
  required; no verification, medical, suitability or rights inference.
- Explicit Workspace Images selection, at most30 unique media IDs, preserving
  customer-selected order. Payload contains only each actual selected media_id and
  expected_sha256 from the scoped library/upload receipt. No image bytes, inferred
  content, credentials or browser-generated source/authority fields in plan inputs.
- MIME allowlist PNG/JPEG only, matching OwnedPlanningImageV1.mime. Explicitly
  reject WebP library/upload results (and video); the broader media library does
  not broaden creative-basis support. Image bytes<=8MiB, positive dimensions<=16million
  pixels. Existing library128MiB quota remains server-enforced. Upload size/name/MIME
  hints are not decoding proof; validate the actual upload response before selection.
  A returned video is never accepted as a planning image.

On edit, render exact saved creative values and selections. Untouched fields retain
original typed values/order/optional fields, including exact price micros; no silent
rounding or whitespace normalization of previously saved strings. Preserve saved
selections absent from the first100 library rows as explicit saved/unverified rows;
never silently remove them or update their expected hashes from newer metadata.
Changed hash requires explicit customer removal/reselection. Newly uploaded rows
may be added from their actual receipt even if the bounded list omits them. Clearly
state list bounds rather than claiming every library item is displayed. No new
pagination/backend route is necessary for this first slice.

## Media Preview And Request Flow

Image upload/preview is optional; selecting zero images remains valid. New-image
selection follows successful real upload only. Preview fetches only same-origin
owned media URLs constructed from the bound workspace and metadata ID. Bound streamed
bytes by the exact declared size and8MiB, verify SHA-256 and MIME, then display a blob
URL and revoke on clear/session/workspace change. No arbitrary URL fetch, video,
remote image tracking, media rights or visual assessment claim. A failed/missing
preview is not a successful image inspection. Saved historical text/proof remains
viewable when current bytes are gone.

`planning.mjs` gains a narrow raw-byte upload function beside its JSON API helper,
using the same original-cookie/epoch checks and CSRF. Do not refactor unrelated
connection flows. Recheck session and synchronously check the turn before rendering
library, upload/preview completion, save or read results. Owner-only editor behavior
remains; 401/403 clears scoped state,409 requires current refresh,503 shows genuine
storage unavailability without optimistic success.

Create/revise uses existing immutable pending-request snapshots and stable request
keys. Include creative only for exact v5. Unknown response recovery retries the
identical body; do not refresh media hashes or regenerate values inside replay.
Server admission validates current workspace/id/hash on NEW saves; exact completed
replay survives later metadata loss. Generate uses the existing endpoint and stable
request key. No advertising publication or spending permission follows from a plan.

## Exact Document Read And Export

Add a v5-only basis section inside the existing safe document renderer, validated
against the response's exact canonical v5 pair, inputs.creative, creative_proof and
creative_composition. Show declared product/list price/facts/restrictions and image
count/dimensions/formats with the original observed_at times and explicit
"Visual Content Not Assessed; Claims Require Review" language. Do not display an
opaque ID as a product name. Generation proof, source currentness and optional
current byte preview are distinct. Do not imply a live preview refreshes evidence.
V1–v4 DOM/output stays unchanged. Existing historical/current/version/correction
navigation and complete server JSON export remain authoritative; no browser-made
proof or regenerated export document.

## Implementation Order And Qualification

1. Freeze classifier/component input/output fields above. Pure DOM tests: v1–v4
   unchanged payloads, exact v5 acceptance, mixed pairs reject, optional/empty product
   and images, decimal precision/bounds, saved selection order/hash preservation,
   safe malicious-text rendering and cleanup after same-owner session replacement.
2. Wire editor/save/revise/media and v5 basis display, with existing pending snapshot
   semantics. No default server policy/store change or new migration.
3. Actual local TLS browser->real API->SQL fixture, explicit injected v5 private
   MediaStore and MockHTTP reporting only: Google chosen-event/product/image create,
   save/generate/current/export; exact saved product and media proof in SQL/export.
   Meta/TikTok no selected observations remain explicit gaps; TikTok still has no
   produced video and its storyboard is a reviewable proposal.
4. Edit/correction preserves untouched exact values and requires explicit media
   removal/reselection. Upload/storage failure, foreign/stale hash, session/workspace
   change, late response and lost-save recovery must not display false success or
   persist mismatched input. Historical media loss still permits exact version export.
5. Run existing default-v3 and v4 browser journeys and pure serialization goldens,
   then both-DB API/browser coverage. Coordinate PG/test resources; no broad aggregate.

Proposed files: planning.html/planning.mjs, new plan-capability/plan-creative-inputs
(and bounded image-preview helper if clearer), narrow plan-selected-captures and
plan-document integration, isolated component/TLS tests and package ledger. No
backend files unless a concrete missing port is demonstrated and separately reviewed.

## Decisions And Remaining Gates

No new owner product decision is needed for this offline UI slice: optional declared
product facts, exact supplied images, editable review, strict evidence boundaries and
planning-only output are already approved. Production activation of a v5 service
and private storage remains an explicit rollout/configuration decision with existing
operational qualification; this proposal does not request or infer that authority.
Expert creative quality and rights/claim review remain distinct from passing the
customer journey. Finishing these controls is engineering work, not a credential
blocker and not permission to change the owner-managed public webpage.

## Frozen DOM And Upload Contract For Independent Browser Tests

Scoped editor host: `#planning-creative-inputs`, hidden for v1–v4. Exact v5 controls:

- `#planning-include-product`: checkbox, "Include Product Details".
- `#planning-product-name`: text, "Product Name".
- `#planning-list-price`: text decimal, "List Price (Optional)".
- `#planning-price-currency`: text, "Price Currency".
- `#planning-product-facts`: textarea, "Customer-Asserted Facts — One Per Line".
- `#planning-product-restrictions`: textarea, "Product Restrictions — One Per Line".
- `#planning-image-library`: rows with `data-planning-media-id` equal to the scoped
  opaque media ID. Each row has a selection checkbox labeled "Select Workspace
  Image N", a Preview Image button, and an optional explicit Use Current Image
  button when its saved expected hash differs from fresh metadata. No automatic
  hash replacement. Selection order is click order; saved order retained.
- `#planning-image-file`: file input, "Upload A Workspace Image", accept PNG/JPEG.
- `#planning-image-upload`: button, "Upload And Select Image". Selecting a file
  alone performs no request. Button posts the file once; only a verified successful
  current-session receipt adds and selects that image (deduplicated by media ID).
  An unknown upload outcome never invents a selected ID or retries automatically.
- `#planning-image-status`: live status text; `#planning-image-preview`: bounded
  current preview container, cleared/revoked on editor/session/workspace changes.

Saved document basis host: `#planning-creative-basis`, emitted only for a genuine
v5 document. Includes product name, exact price, facts/restrictions, supplied image
count and original observation times with the explicit unassessed/review notice.
Existing planning save/generate/current/version/export button IDs remain unchanged.

No new API or TLS test implementation belongs to the component author. Browser
agent owns separate Python/JS actual TLS journey files; component author owns new
component tests and production HTML/JS. Both consume these stable selectors.
