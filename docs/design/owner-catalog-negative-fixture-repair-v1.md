# Strict-Valid Catalog Substitution Negative — Fixture Repair

Source-only proposal after Acceptance09: six passed, seventh SQLite case failed during
its adversarial candidate construction,21 unrun. Frozen production `f4e3b72` is not
modified. No tests or candidate-construction experiment executed in this assessment.

## Actual Failure Boundary

The fixture mutates an independent Google campaign's starts_native in both the full
candidate catalog and the Google owner's witness catalog, then asks PlanVersion to
validate. A witness observation digest commits the ENTIRE catalog, including campaigns
outside that owner. The saved resolved intent still carries its original observation
digest. Review.exact → resolve_google_daily_budget_intent rejects this mismatch before
repository.save_generation or the intended fixed409 assertion is reached. The old public
resolver also checked this exact digest; this is not evidence of a kernel regression.

Rehashing the witness would require a different expected_observation_digest in the saved
input's resolved intent. Altering that input/ticket would hit earlier saved input binding
or change the fixture's trust boundary. Do not perform such rewrites, and do not accept
an arbitrary earlier409 as equivalent coverage.

## Minimal Repair: Linked Meta Catalog Outside Google Witness

Reuse existing `add_owned_meta(..., linked=True)` before the actual input POST in this
one test. It performs actual owned Meta catalog HTTP acquisition, adds its account and
one campaign allocation plus another exclusion to the original request. The original
nonempty Google owner intent and its witness remain unchanged. No shared helper change.

The composer wrapper first calls the real OwnerReviewPlanComposer normally. It then
copies the returned full document and changes exactly ONE native scalar in the linked
Meta catalog only, selecting it by full account identity/platform, not tuple position.
Use `MetaSettingsV1.spend_cap_native` of one Meta campaign: a different nonnegative strict
integer (e.g.1 when None, otherwise original+1 within Amount bound). This field is native
unqualified observation data, not identity, target selection, metadata status, schedule,
Google membership, or an action instruction. Preserve original opaque inventory/composite
commitments to exercise the existing full-content comparison under a structurally valid
but untrusted declaration. Do not reproject or claim authentic provider acquisition for
the substituted value.

Construct the altered `CatalogEvidence` through its real model validator, then construct
the whole `PlanVersion` through its real validator. These must succeed before the wrapper
returns; a failure here is a fixture design failure, not a save-boundary success.
The source schemas expose no cap-derived catalog identity or Google-owner invariant:
MetaSettingsV1 permits optional nonnegative native integer cap; composite identity commits
opaque original inventory/metadata digests, while the intended boundary independently
compares complete catalog JSON. Execution must demonstrate this expectation, not assume it.

## Exact Assertions And Ordering

Before/after construction assert identical canonical bytes for:
- Original saved input and its nonempty Google intent; kwargs ticket and actual bundle.
- Complete Google catalog, Google owner witness/proof and action.
- Every catalog except the selected Meta one; every Meta catalog field except the one
  chosen spend_cap_native leaf. All full account/native identities and targets unchanged.

Assert new candidate strict validity, changed full document digest, and changed Meta
catalog full JSON. The actual evidence bundle and persisted input/catalog receipts remain
original. No test updates them to accommodate the malicious candidate.

On generate, expected source order is unchanged: repository entry validates this strict
candidate; original ticket/input/head and reference/target bindings pass; owner bundle
assertion `_linked` derives original linked catalogs from actual evidence and compares
complete JSON against candidate.google_budget_input_catalogs. This exact comparison
must produce409 `owner review differs from actual collected evidence` before paid/current
rechecks/CAS/writes. The test must assert the substitution callback completed once and
that intended owner-bundle helper was entered; it must not accept planning_authority_expired
or another409. Planning heads/versions/dependencies/receipts and financial effects remain
exactly unchanged. Record actual native call list if the existing test fixture exposes it;
no write transport is added.

Only `tests/test_owner_review_runtime_api.py`'s existing negative function changes, with
its fixture evidence ledger. Parent assigns the author; no production changes or weakening.
Existing pure observation-digest refusal cases already protect the original invalidity;
no repeated API negative for the obsolete construction is required.

## Bounded Continuation, Not Retry Of Completed Work

After source review and exact manifest preparation, proposed continuation is the repaired
SQLite node7 plus21 never-run nodes:22 total, excluding all six already passed IDs from
Acceptance09's preserved ordered manifest. Stop first failure with its original traceback,
no automatic retry. An exact-node set difference and source hashes must be recorded before
execution. No run is authorized by this proposal itself. Results remain split across the
unchanged six passes and repaired-source remaining cohort, not a fabricated single28pass.
