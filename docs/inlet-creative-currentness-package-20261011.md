# Creative Metadata Currentness — 2026-10-11

Status: implemented and qualified on `codex/inlet-w1-followup`;
frozen commit `841b587` passed independent final review with no P1/P2 findings.
Interface `40b6ceb`.

`capture_creative_retained_source` checks a genuine v5 document against current
owned image metadata within the caller's clean root transaction. It requires the
current viewer's READ_ROLES authority, current goal confirmation and privacy revision;
it does not require paid access or the original generator identity. It rejects
changed/missing/foreign metadata, retains the original observation timestamps and
returns the immutable creative-basis witness. It preserves both SQLAlchemy Session
and underlying Connection transaction identities, disables autoflush, and samples
UTC expiry after SQL guards/locks. The caller remains responsible for its fresh
identity-provider fact, workspace-first lock and final authority check.

This is metadata currentness, not current blob availability. It performs no provider,
storage, decoding, commit or other external operation. Ordinary image metadata loss
makes currentness stale while complete immutable historical dependencies remain
valid. Semantic privacy erasure still removes the historical graph.

The fixture uses actual local reporting/capture APIs, owned media upload/inspection,
the genuine composer and explicit test-only persistence. Optional image counts use
distinct valid PNG bytes because media upload deduplicates equal hashes.

Evidence directory: `/workspace/inlet-evidence/20261011/creative-currentness`.
Initial SQLite run `sqlite01` ended with 5 passed, 22 failed and 2 errors
(183.102s); the focused `viewer02` attempt failed its one fixture setup
(11.991s). These were test-harness errors: duplicate image selection after
upload deduplication; a new viewer fixture copied an intentionally omitted session
creation field from the principal snapshot; and assertions expected HTTPException
instead of the existing RetainedSourcesChanged domain exception. These attempts
remain retained. Production implementation was unchanged by these repairs.
Initial mypy caught test import/export and Any narrowing errors; corrected tests
retain the production exception distinction.

Whole Ruff and configured no-path mypy passed (`ruff04`, `mypy04`, 1,400
source files). Corrected `both03` passed **58 tests** across SQLite/PostgreSQL
with zero skips/failures/errors (416.892s). Two warnings are expected from deliberately
replacing the underlying SQL transaction in fault-injection tests. The focused
`assertion04` metadata-loss/history cases passed **2 tests** (17.771s) after the
final test type-narrowing edit; this is overlapping coverage, not a separate full suite.
`git diff --check` passed. No predecessor full qualification was rerun or relabeled.
No v5 service registration, default-policy change, deployment, live provider calls,
spend or advertising writes are included. Q01–Q16 human usefulness gates remain.
