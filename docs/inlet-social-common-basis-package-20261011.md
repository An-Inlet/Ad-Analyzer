# Provider-alone Common Basis fixture — 2026-10-11

Test-only child of `afe4c15`, implementing the reviewed provider-alone seam in
`docs/design/planning-creative-basis-interface-v1.md`. No production code, public
policy registration, selected social mapping, typed creative media, or authority
changes.

`prepare_q16_basis` adds optional `native_account_factory(engine, workspace_id,
patch, calls) -> account_id`. The default is the original Google fixture. The
existing `prepare_q16_case` signature, wrapper, dated clocks and behavior remain
unchanged. The callback only bootstraps the owned native source fixture; it cannot
supply a principal, authority result, catalog, plan, proof or reporting evidence.

`tests/social_common_basis_fixture.py::prepare_social_common_basis(...,
platform="meta_ads"|"tiktok_ads")` returns `(Q16Basis, exact_body, calls)`. It uses
the original owner session, actual Shopify baseline/import and goal confirmation,
actual owned image upload and same frozen USD/New York September/August reporting
and November $12,000/$8,000/$1,000 balanced goal basis. Meta has two campaigns and
two observed ad sets; TikTok has one regular-family campaign/ad group. Real owned
Vault/context/native HTTP collectors and metadata parsers consume injected local
MockHTTP responses from the existing native-reader fixtures. Both catalog scopes
remain explicitly partial. No video or campaign metrics/completion is seeded.

The actual saved-input/generate/export path uses explicit empty
`selected_reporting` and private canonical v4 injection. It retains
`unsupported_selected_mapping`, null selected capture proof, absent traffic pin,
and no reported metric references. There are no inferred Google statistics or
social selected-event capabilities. Tests assert native campaign identities,
observed child locations, campaign-only actions, one creative brief, no native
budget proposal, no execution records, original owned image bytes and exact export
identity. A creative brief is a production proposal, not proof that the existing
image is suitable or a video exists. Full Q03/Q04 and human usefulness remain open.

## Evidence

Durable directory: `/workspace/inlet-evidence/20261011/social-common-basis`.

- `sqlite01` retained: test incorrectly counted the additional creative action as
  a third campaign. Fixed assertions separately count campaign reviews and the
  single creative action/brief; no output or implementation change.
- `sqlite02` retained: test expected `traffic_pin: null`; the approved omission
  serializer deliberately leaves absent traffic pins out. Assert exact absence.
- `sqlite03`: 2 passed, 2 PostgreSQL cases deselected, 5.89s.
- `both01`: 8 passed, zero skips, 23.53s: four social cases and four unchanged
  Q16 Google progress/privacy preservation cases on both databases.
- Final whole Ruff, configured mypy (1,369 source files), and diff checks passed.
- Eight actual social document/export JSON packets copied with SHA256 manifest.

Tests use explicit unique scratch basetemps, durable JUnit, `--durations=20` and
the existing per-test isolated-schema disposable PostgreSQL fixture. No database
reset, live network, Full, hosted CI, remote push, deployment or ad mutation.
Successful social cases save actual synthetic document and export JSON for later
creative work; durable copies and a hash manifest identify case/database. No
cookies, private grants or credentials are part of those public output artifacts.
