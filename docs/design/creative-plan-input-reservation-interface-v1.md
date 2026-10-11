# Reserved Creative Plan Inputs V1

First integration step after standalone creative contracts/readers. No v5 runtime
registration or default change. Preserve every v1–v4 document's existing bytes.

Add optional `creative: CreativeInputV1 | None = None` to `CustomerInputs` and
`PlanInputRevision`. Serialization omits it when None, including nested JSON;
explicit non-null empty creative input remains meaningful and is never dropped.
Revalidate nested copied models. Bind optional price currency to the confirmed
goal when preparing/resolving the owned input; media ownership remains the later
reader's responsibility, never inferred from a valid ID/hash.

`input_resolution.prepare` copies the exact typed creative value. `resolve` checks
that prepared and requested creative inputs still match before returning input
data. Existing request digests/replay/CAS include explicit creative data naturally;
omission must preserve old request/document hashes.

Add a dependency-light canonical version reservation and validator: only exact
`inlet.descriptive-review.v5` / `inlet.descriptive-planning.v5` may accept non-null
creative inputs, and that pair requires an explicit `CreativeInputV1`. Other pairs
with null creative inputs keep their existing validation path; this helper does
not recognize unknown policies or bypass their separate closed policy validation.
All v1–v4 pairs reject non-null creative inputs, including an empty object.

Apply this guard to plan create/edit admission and generation, and to existing
pure composers/PlanVersion validation so no older composer silently ignores typed
creative inputs. Malformed input retains existing422 validation handling;
unsupported policy admission and incompatible saved generation use the existing
409 conflict handling, consistently with selected inputs. No new public
configuration or service policy acceptance is enabled.

Validate legacy Python/JSON and digest goldens; null omission versus explicit
empty/value; copied-model and currency failures; exact policy-pair gating; actual
customer API rejection before persistence/native reads on both databases. Preserve
existing selected-input behavior and request replay/CAS. Run whole Ruff/configured
mypy and independent review. Later v5 bundle/selected-capability/proof wiring is a
separate package; reserved fields do not make v5 available to customers.
