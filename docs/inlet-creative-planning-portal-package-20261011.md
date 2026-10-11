# Private V5 Planning Portal Package — 2026-10-11

Base: root `bff7fb0`, preserved through local merge `0ef9c6c`. Selector contract
`f688477` extends the approved `b5bbb51` / `3219464` interface. Production remains
private and explicitly configured; default v3, older payloads and all advertising
execution authority are unchanged.

Implemented capability-gated structured product/name/exact micros price/facts/
restrictions and ordered owned-image choices. Saved values and out-of-list selections
survive edits; fresh hash changes require explicit replacement. PNG/JPEG only,
8 MiB / 16-million-pixel bounds; unsupported WebP/video cannot be selected. The
library remains explicitly bounded to 100 items and an unavailable response is an
error, never an empty library.

Uploads require an explicit button, original session checks, CSRF, and matching
successful metadata/content hash before selection. Unknown outcomes do not invent
IDs or automatically retry. Previews read only owned same-origin bytes with bounded
streaming, MIME/size/hash checks, abort/expiry and original-session checks. Editor
cleanup aborts work and revokes object URLs. Product/selection request snapshots use
the existing immutable request recovery mechanism. The saved basis renders original
observations and all six price fractional digits, without visual/rights/claim proof.

Reviewed backend exception: existing CSP allowed blob video but not blob images.
Parent and independent reviewer approved adding only `img-src 'self' blob:` to
`customer_content_security_policy`; all other directives are preserved and tested.
No API, storage, policy, database or service changes.

## Checks And Preserved Evidence

Evidence: `/workspace/inlet-evidence/20261011/creative-planning-portal/`.

- Initial component + existing target/document cohort: 4 passed, 1 failed, 0 skips,
  9.743s (`components-initial.xml/log`). Failure was the new test reusing a live
  DataTransfer whose files were cleared by the prior successful upload. The delayed
  upload test now creates a fresh file list and asserts the request actually began;
  production behavior was not weakened.
- Repaired new component: 1 passed, 0 skips, 3.473s (`components-repair.xml/log`).
- Final component + exact CSP + existing disabled/enabled identity CSP checks:
  4 passed, 0 skips, 2.914s (`components-final.xml/log`).
- Whole Ruff passed; configured no-path mypy passed, 1,412 source files.
- Node syntax checks passed for new modules and planning entry point; diff check clean.

Component coverage includes exact legacy omission, v5 empty inputs/selected choices,
price precision/bounds, literal malicious text, saved ordering/out-of-list retention,
changed hash explicit review, WebP rejection, upload selection only after response,
late-result invalidation, session fence, original saved basis, bounded byte preview,
hash mismatch and upload CSRF/content receipt. Existing legacy rendering tests pass.

Actual authenticated TLS/API/database journey tests belong to the independent browser
package and are pending on this production freeze. Component mocks do not establish
that qualification, live provider readiness, visual quality, usage rights, or private
v5 production activation. No remote pushes, hosted CI, live calls or deployments.

## Independent Review Repair

Reviewer found an exact-value P2 in the initial portal freeze: changing one product
control reconstructed all saved fields, trimming untouched names and splitting
untouched multiline array entries. The component now compares each field separately
and preserves its original typed value when unchanged; only edited controls parse.
Saved fixed schema/provenance/review metadata and unchanged list-price metadata also
remain intact. A DOM regression changes only price in a saved whitespace/multiline
product, then edits name and facts independently and asserts all untouched fields.

Narrow repaired cohort: 2 passed, zero skips (`field-preservation.xml/log`). Whole
Ruff and configured mypy (1,412 files) passed again; Node syntax and diff checks clean.
No server, authority, session, or legacy-policy behavior changed. Final actual browser
qualification is held until this repair is reviewed and consumed.
