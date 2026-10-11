# Standalone Creative Retained Proof — 2026-10-11

Base `980f1ef`, interface `9a32b9a`. Pure proof module and focused tests only;
no document, SQL, capability, service or default changes.

The proof retains the exact owned image basis and ordered media identity
commitments. Its factory checks the private collection's complete ticket and saved
creative input. Creator and creation-time changes affect identity commitments;
observation-time changes affect the complete proof but not source-binding digests.
Creator/session/ticket fields and raw bytes are not exposed in the proof.

Input binding checks exact requested intent, workspace, confirmed currency and
strict privacy revision. Both digest methods revalidate copied objects. Distinct
fingerprint domains separate complete row identity, creative source binding and
the full typed proof. UTC row timestamps are serialized explicitly as ISO strings.
Empty image selections still have explicit retained proof.

Checks:21 focused pure tests passed,0 skips/failures/errors,6.055 seconds, including
both fresh-process import orders. Whole Ruff and configured no-path mypy passed
for1,385 source files; diff check passed. Source review provisionally closed with
no P1/P2 before these terminal checks; frozen-hash closure requested separately.
Evidence `/workspace/inlet-evidence/20261011/creative-retained-proof/` contains
JUnit/logs/statics. Initial six Ruff line-length failures were retained and fixed
by formatting; no runtime failure was suppressed.

The private collection dependency `980f1ef` (author87954cd) was independently
reviewed closed with106 SQLite/PostgreSQL reader cases passed,0 skips,154.88seconds.
Those are separate author cases, not this package's proof tests.

Parsing proof does not authenticate ownership. Exact SQL finalization, retained
proof/dependency persistence, history/currentness and privacy remain required
future consumers. Temporary creative PlanVersion rejection remains; defaultv3,
v5 registration refusal and all live/hosted/push/spend/merge/deploy holds persist.
