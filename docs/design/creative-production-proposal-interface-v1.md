# Standalone Creative Production Proposals V1

Depends on the reviewed `CreativeBasisV1`, existing owned catalog contracts and
planning inputs. This is pure composition, not reader/persistence/runtime wiring.
Keep existing ManualAction, CreativeBrief and PlanVersion v1–v4 bytes unchanged.
Later integration uses a separately reviewed canonical private v5 pair, with
default v3 unchanged. Parsing or composing any value grants no access or authority.

## Pure Port And Exact Bindings

`compose_creative_proposals(inputs: PlanInputRevision,
catalogs: tuple[CatalogEvidence, ...], basis: CreativeBasisV1,
references: CreativeCompositionReferencesV1, *, first_priority: int)
-> CreativeCompositionV1`.

`CreativeCompositionReferencesV1` contains distinct bounded keys for basis,
customer context and policy, plus their exact digests and the full canonical
`PlanningCompositionPolicy`. Require basis digest equal the revalidated basis,
customer-input digest equal revalidated `inputs.digest()`, and canonical policy
pair `inlet.descriptive-review.v5` / `inlet.descriptive-planning.v5` with exact
default policy fields/digest. This does not register v5 in existing capability
dispatch. Every supplied catalog must validate, belong to an exact input account
and have a unique account/key. References cannot collide with catalog keys.
Missing account catalogs remain explicit limitations, never fallback identities.
Require basis workspace, currency and privacy to agree with inputs and every
supplied catalog privacy revision. All nested values are revalidated.

## Output Contracts

New `CreativeCompositionV1` holds basis digest, up to30 proposals and bounded
limitations. Each `CreativeProposalV1` contains existing ManualAction and
CreativeBrief plus `CreativeProductionV1`. All inherit planning-only authority.

Production fields: ordered `source_images` (PlanningMediaSelectionV1), optional
`selected_image_id`, `source_image_status` (`owned_bytes_observed` or
`not_supplied`), `deliverable` (`image_creative` or `video`), fixed
`deliverable_status=production_required`, `visual_assessment=not_assessed`,
`basis_evidence_key`, and ordered `storyboard`.
Each shot contains bounded `purpose`, `capture_instruction`, `proposed_caption`.
Meta has zero storyboard shots; TikTok exactly introduction/demonstration/CTA in
that order. Validate action/brief/production keys and targets coherently; proposals
must bind exact basis images, never client-authored availability. No proposal
claims an already produced deliverable, rights, placement approval or suitability.

## Composition Rules

Only Meta/TikTok creative proposals in this package. Other platforms receive an
explicit unsupported-creative-policy limitation; existing Google plans unchanged.
Use included exact campaign targets from the catalog, applying exclusions before
selection. If all campaigns are excluded or absent, defer instead of choosing an
account fallback. Deterministic account/campaign ordering is administrative, not
a ranking of performance. A proposal may state that its scope was selected for
review and does not establish the best campaign.

Zero capacity produces no proposal; unconfirmed capacity, missing typed product,
or unresolved freeform constraints explicitly defer. One proposal consumes one
finished deliverable from the global confirmed capacity; three video shots are
components. Exhausted capacity defers remaining accounts with a clear limitation.

Meta: identify the first selected image as source bytes observed at the recorded
time; if none, request an image without inventing one. Customer must inspect product
depiction, rights, crop/legibility, current placement and destination. Use typed
product name and exact optional price, subject to offer verification. Prepare one
image creative with concrete copy/layout/review steps.

TikTok: no video witness is supplied by this image-only basis, so video production
is required; never claim no video exists anywhere in the customer's library.
Introduction shows the actual named product; demonstration uses a supplied fact
with an explicit substantiation prerequisite, or requests a fact before filming;
CTA invites viewing product details. Give caption/edit/review steps. Do not invent
features, thermal/leakproof/health/durability claims, testimonials, timings, Spark
authorization, video assets or sales effects. Treat customer restrictions verbatim
as required review constraints, never erase them.

Keep native_budget null, proposed_fields empty and expected effect uncertain.
Reference catalog for location, customer context for declared facts, and basis for
observed image bytes only. Preserve catalog partial coverage and lack of qualified
performance evidence in limitations; no budget transfer or causal inference.

## Validation

Pure tests cover exact binding/tamper rejection, exclusions, capacity0/1/unknown,
constraints, missing product/image/fact, currency/price precision, no-video wording,
storyboard order, strict typed values, target identity and partial coverage.
Use actual retained social catalog fixtures where practical; fabricated pure
inputs are not claimed as API qualification. Whole Ruff/configured mypy before
commit; independent review. Actual owned reader and eventual retained v5 API
integration remain separate packages and require their own qualification.
