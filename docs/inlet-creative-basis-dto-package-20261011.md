# Standalone Planning Creative Basis Contracts — 2026-10-11

Base `afe4c15`; implements only the first package of the approved
[creative basis interface](design/planning-creative-basis-interface-v1.md).
Production addition: `app/planning_documents/creative_basis.py` only.

## Frozen Interfaces

All classes inherit the existing frozen, extra-forbidden, recursively revalidated
planning-only primitives. `digest()` revalidates the complete object and uses the
existing domain-separated canonical document fingerprint.

- `CustomerListPriceV1(micros, currency)`: existing strict bounded Amount/Currency.
- `CustomerProductV1(name, list_price=None, customer_asserted_facts=(), restrictions=())`:
  each text tuple max20; fixed customer-supplied provenance and required claim review.
- `PlanningMediaSelectionV1(media_id, expected_sha256)`: no caller ownership or location.
- `CreativeInputV1(product=None, media_selections=())`: ordered max30, unique media IDs.
- `OwnedPlanningImageV1(workspace_id, media_id, sha256, size, mime, width, height,
  created_at, observed_at, privacy_revision)`: PNG/JPEG only,8MiB/image,16million pixels,
  fixed `visual_assessment=not_assessed`; strict aware timestamps normalized to UTC.
- `CreativeBasisV1(workspace_id, goal_currency, privacy_revision, requested, images)`:
  exact ID/hash/order correspondence, same owned scope/privacy, matching price currency,
  and128MiB total library bound. Images are ordered max30.

The five explicit schema tags are those in the approved interface. List price is a
nested value object. All objects explicitly deny advertising writes/spending authority.
Ordered collections accept JSON arrays or tuples, rejecting unordered collections.
Numeric, boolean, naive and non-ISO timestamps cannot cross the instant boundary.

A parsed witness is not evidence that an authenticated reader checked ownership or
bytes. This package does not inspect image pixels, establish suitability/rights,
resolve storage, update current input/API/composer/policy, add a migration, or enable
any runtime. Those boundaries still require their reviewed dependent implementations.

## Checks

Evidence: `/workspace/inlet-evidence/20261011/creative-basis-dto/`.

- Initial pure cohort: **47 passed**, zero skips,0.123 seconds (`pure.xml`).
- Additional strict price/schema cases: **6 passed**, zero skips,0.097 seconds
  (`price-schema.xml`). Includes zero price, booleans/coercion/overflow and copied tags.
- Whole Ruff passed. Configured mypy passed for **1,369 source files**.
- `git diff --check` passed.

No PostgreSQL, live/provider calls, hosted tests, remote push, merge or deployment.
Existing v1–v4 consumers and default v3 remain untouched.
