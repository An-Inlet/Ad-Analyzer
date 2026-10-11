# Q08 standalone empty-query proof layer

This package contains only shared model extraction, new standalone witness/proposal
contracts and pure tests. It does not change composers, PlanVersion validation,
repository consumers, service/API wiring, defaults or provider/runtime activation.
The later full document/source/prerequisite validator remains required before the
new account-preparation output can be used by genuine generation.

`CatalogEvidence` is moved unchanged to `catalog_evidence.py` and explicitly
reexported by ports as the identical class. Existing standalone schema and nested
Python/JSON bytes/digests are checked against pre-change hashes captured in
`tests/fixtures/q08_empty_proof/legacy-goldens.json`. This includes Meta/TikTok full
creative documents and composition, plus independent-process import orders.

`EmptyDeclaredCatalogWitnessV1` retains the complete actual typed catalog/reference
and exact account investigation key. It recognizes only the actual Meta limited
SDK-status coverage tuple, empty native/metadata/composite arrays, strict original
aware times, exact UTC local and cross-node chronology, and a256KiB bound. It does
not reconstruct opaque raw inventory hashes or establish provider-wide emptiness.
The new proposal fields are omitted recursively for the old campaign path; account
proposals require Meta image production, owned image selections, matching full
account/catalog reference and exact prerequisite key. Full document-level existence,
zero ceiling, retained source and actual collected-bundle checks are intentionally
left to the next approved consumer layer.

Persisted SQL currentness cannot discover out-of-band provider campaigns. Fresh
acquisition is required to observe those changes; historical proof retains the
original declared-query observation without a new provider lookup.

## Evidence

Durable directory: `/workspace/inlet-evidence/20261011/q08-empty-proof`.

- `before-goldens.json`: pre-change existing schema/Python/JSON/digest hashes.
- `pure-01`: five passed before the synthetic proposal fixture failed because it
  removed the existing required brief claim reference. Fixed the fixture to retain
  its customer-fact key and action linkage; no product validator was relaxed.
- `pure-02`:111 passed,0 failures/errors/skips,13.103s, new module plus existing
  creative composition and document cases.
- Independent review identified missing cross-node UTC reporting-window joins:
  same-ZoneInfo folds can compare equal in the unchanged legacy models. Added
  explicit reference/native vs metadata UTC joins only in the new witness.
- `pure-03`:29 passed,0 failures/errors/skips,4.537s. Two rehashed whole-witness
  regressions demonstrate the old model accepts equal wall times while the new
  witness rejects differing UTC reporting ends. Offset-equivalent timestamps and
  original serialized offsets remain supported. This overlaps the new-module
  cases from pure-02; it is not140 distinct tests.
- Initial static findings: one long subprocess string and a nullable fixture
  account annotation. Fixed without behavior changes. Final whole Ruff passed;
  configured no-path mypy passed1427 source files; diff check passed.

Reusable qualified pure helpers in `tests/test_empty_catalog_contracts.py`:
`empty_evidence() -> CatalogEvidence`, `witness() -> EmptyDeclaredCatalogWitnessV1`,
`proposal() -> CreativeProposalV1`. They are explicitly synthetic pure fixtures,
not proof of customer ownership, actual HTTP acquisition or Q08 end-to-end quality.
No database tests, live calls, external artifact sharing or expert assessment ran.
