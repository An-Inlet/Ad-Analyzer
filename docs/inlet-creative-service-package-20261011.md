# Private Creative Planning Service Package — 2026-10-11

## Scope

Implements the reviewed [service interface](design/creative-planning-service-interface-v1.md)
including its owned-media admission addendum. Base includes reviewed currentness
841b587 and retained dispatch 4672d14. Canonical v5 is a distinct private reporting
mode using the real combined reporting/image reader and creative composer. Default
v3, existing v1-v4 policy documents and advertising execution authority are unchanged.
V5 requires an explicitly supplied MediaStore; default routes do not resolve one.

New create/revise requests check exact owned media IDs and expected hashes in both
input-save transactions, after exact completed-request replay. These SQL checks are
not image observations. Generation still reads/hash-checks/decodes actual bytes,
binds the exact private collection proof and references, and repeats selected,
image and selected SQL checks before complete retained witnesses and atomic writes.
Unexpected provider/clock/database errors are not normalized by a broad v5 catch.

The repository rejects substitution of an otherwise valid private media creator
commitment between collection and candidate. Existing atomic CAS/version/dependency/
receipt/expiry guards remain active. Completed replay uses retained immutable history
before current media checks, allowing later media loss without claiming fresh reads.

## Qualification

Durable logs/XML: `/workspace/inlet-evidence/20261011/creative-service/`.

- `initial.xml`: 71 passed, zero skipped, 10.189s: new SQL admission on SQLite and
  PostgreSQL plus pure creative composer/document tests.
- `policy-regression.xml`: 186 passed and two stale expectation failures, zero skipped,
  12.885s. One expected the newly recognized v5 to remain unregistered. The other
  already expected v4 to be unregistered on the base despite its existing registry.
  Only those capability assertions were corrected; no document snapshots changed.
- `repairs.xml`: both corrected assertions plus private repository substitution
  rejection passed (3 passed, zero skipped, 0.478s).
- Initial whole mypy passed1402 files; later whole mypy found a test-only import of
  `repository.authority` not explicitly exported. Direct authority import corrected
  it; `mypy-repair.log` passed1407 files including three temporary parent-owned
  integration test files. Whole Ruff passed and diff check passed.
- `legacy-owned.xml`: 24 passed, zero skipped, 169.347s: actual v4 HTTP range/capture/
  input/generation/replay on both databases, genuine v5 selected-reader contexts and
  owned combined-reader capability assertions. Existing v4 byte checks are retained.
- `final-pure.xml`: unchanged default constructor plus corrected test import's
  repository binding case passed (2 passed, zero skipped, 2.203s).
- Independent review found an omitted repository lower-bound check on candidate
  generation time, despite the composer enforcing it. Added v5-only UTC checks
  against original ticket preparation, selected collection and every image
  observation before authority or writes. `time-binding.xml`: private identity and
  zero/one-image timestamp substitution rejection passed (3 passed, zero skipped,
  0.620s). Root owns actual API atomic-no-effects regression for this repair.
- Parent-owned temporary probe files removed. Final whole Ruff passed
  (`ruff-time.log`), configured no-path mypy passed1404 source files
  (`mypy-time.log`), and `git diff --check` passed.

Root independently owns actual HTTP v5 generation/export/history/correction,
rollback and lifecycle qualification. Its temporary fixture/API/lifecycle files are
not part of this commit; early probes do not substitute for final integrated tests.
No live accounts, provider qualification, deployed default switch, public claims,
advertising changes, remote push or hosted checks occurred.
