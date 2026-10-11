# Pure Creative Plan Document — 2026-10-11

Base `9a89916e78c5fadd001c0416cc700cf3f651da19`; implements the reviewed
[document interface](design/creative-plan-document-interface-v1.md).

PlanVersion adds optional creative_proof and creative_composition, omitted when
None. Exact v5 requires both and selected reporting proof. The document-safe helper
`creative_basis_reference(proof, inputs, valid_until)` binds the complete proof,
saved input, privacy and observation times. Exactly one matching creative reference
is required. Typed proposals must match every creative action/brief; global customer
capacity and existing target, evidence, ownership and document constraints remain.
All other policies reject creative proof/composition/references.

Only v5 normalizes generated/validity and reference instants to UTC before nested
bounds validation; saved input creation is compared in UTC without rewriting saved
inputs. This handles DST folds without changing legacy serialization. Parsing is
not owned collection, historical verification, suitability or runtime authority.
No selected composer, capability, service, history, persistence or default change.
The reserved-v5 negative test now requires missing proof/composition rejection.

## Evidence

Durable directory: `/workspace/inlet-evidence/20261011/creative-plan-document/`.

- Initial pure26tests passed (`pure.xml`).
- Combined document/input/legacy-composer/selected-composer/child-location cohort:
  112passed,1test assertion failure, zero skips,19.811seconds (`combined.xml`).
- The failure was object equality between an ambiguous named-zone input datetime
  and its JSON-parsed fixed-offset equivalent. The test now requires identical
  immutable serialized bytes and digest; corrected fold case passed (`fold-final.xml`).
  Invalid UTC input/generation/observation/expiry order cases already passed.
- Expanded exact binding/foreign-target/dropped-proposal cohort26passed (`expanded.xml`).
- All canonical v1–v4 explicit-null omission test passed (`legacy-null.xml`).
- Direct pre-change/current serialization comparison uses the exact base documents.py
  retained as `base-documents.py`. Fresh processes produce identical SHA256 and
  document digests for genuine canonical v1/v2/v3/v4 composer fixtures:
  `legacy-before.json` equals `legacy-after.json`. No golden snapshot was refreshed.
- Whole Ruff and configured no-path mypy pass; final logs retained. Initial test
  typing and lint failures remain recorded. Diff whitespace check passed.

Pure fixtures demonstrate structural validity only. No PostgreSQL, provider/network,
remote push, hosted checks, Full, merge, deployment or runtime activation.
