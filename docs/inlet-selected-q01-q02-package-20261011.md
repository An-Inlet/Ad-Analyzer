# Selected Q01/Q02 Common Basis package — 2026-10-11

This test-only package starts at `32fb055` and consumes the independently reviewed
child-location composer commit `bb3b5f1` (local cherry-pick `0fc1ac6`). It changes no
production policy, public default, service, schema or authority gate. Canonical v3
remains the public default; tests explicitly inject the real canonical v4 service.

## Fixture and actual path

`tests/q16_fixture.py::prepare_q16_basis` returns `Q16Basis` with owned workspace,
confirmed goal/revision/confirmation, store, account, uploaded image ID/hash, and
exact plan creation body. Existing `prepare_q16_case` remains a wrapper performing
the same create/generate and returning the same `Q16Ids`; October/November dated
clock behavior is unchanged.

`tests/selected_q01_q02_fixture.py::prepare_selected_common_basis` calls that
preparation at its October stage. The same original owner session/account then
uses actual range publication, event options, exact event confirmation, selected
capture, saved input and generation APIs. Only identity/provider MockHTTP and the
private canonical policy constructor are injected. No captured proof, generated
plan or execution record is seeded. The inherited Q16 native-account bootstrap is
explicit fixture setup; its owned Vault and actual native collectors remain used.

Tests assert USD/New York September reporting, August comparison, November
$12,000 merchandise net sales goal, actual complete $8,000 Shopify baseline,
$1,000 November ceiling, balanced aggression, $25 reusable travel mug facts, one
uploaded image's ownership/content hash, and no approved health/testimonial claims.
The three separate cases report 100 clicks/$100 and selected count 10, explicit
complete zero, or missing. They assert exact Mug Campaign and Mug Ad Group
locations, campaign-only metrics/actions, no proposed native budget change,
original-session continuity, no execution records, and exact retained/exported
plan equality. The uploaded image is not claimed to be consumed by typed creative
analysis or visually suitable. Generated documents remain `not_expert_qualified`.

## Checks and retained failures

Durable evidence: `/workspace/inlet-evidence/20261011/selected-q01-q02`.

- `sqlite01`: first SQLite failure correctly rejected range receipt because the
  generic customer fixture disables foreign keys. The new selected helper now
  enables and asserts SQLite FK enforcement before setup, matching existing
  selected fixtures. No schema/trigger bypass.
- `sqlite02`: capture correctly rejected extra named-event fields from the mock
  response to the strict two-field ownership query. Mock now returns the exact
  query-specific documented shape; parser unchanged.
- `sqlite03`: 3 passed, 3 PostgreSQL cases deselected, 26.12s.
- `both01`: 10 passed, zero skips, 68.63s: six Q01/Q02 cases plus four unchanged
  Q16 progress/semantic-erasure preservation cases across SQLite/PostgreSQL.
- `ruff02` retained a long assertion-line failure; literal split without semantic
  change, then whole Ruff passed. Configured mypy passed 1,366 source files.
- `artifacts01`: final six both-DB cases passed, zero skips, 56.88s; 12 actual
  document/export packets retained with SHA256 manifest.
- Final whole Ruff, configured mypy (1,366 files), and diff checks passed.
- First artifact-copy glob matched no files because pytest truncated its directory
  name; assertion refused the incomplete copy. Corrected directory enumeration
  copied all 12 files and wrote the manifest; no test/source change.

Actual bounded test commands use `/workspace/inlet-venv/bin/pytest`, explicit
unique `/tmp/inlet-q01-q02-*` basetemps, durable JUnit paths and `--durations=20`.
Both-DB cases use the existing explicitly disposable local PostgreSQL test fixture
with per-test random schemas; no shared/root database reset. No Full, remote,
hosted CI, live provider access, ad mutation, deployment or expert qualification.

## Review artifacts

Each successful new case writes only the synthetic generated document and public
export packet into its test scratch directory. Copies retained under the durable
evidence `artifacts/` directory identify case and database. They contain actual
API output, not a handcrafted example. Auth cookies, access/refresh tokens and
private source grants are not included. Separate human review must assess
usefulness; the automated assertions do not establish the full quality matrix.
