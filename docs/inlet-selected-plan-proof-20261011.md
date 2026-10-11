# Selected Plan Retained Proof Types — 2026-10-11

The reserved v4 document now requires an immutable per-account proof matching
persisted capture selectors. It records original source/head/capture commitments
so historical validation can distinguish stale history from broken retained data.
Old documents omit the new field and preserve exact Python/JSON/canonical hashes.
Shared source/pin types retain backward type-identity exports.

Independent source review closed this pure DTO slice. Evidence:
`/workspace/inlet-evidence/20261011/selected-plan-proof01/` records **119 passed,
zero skips/errors/failures, 2.520 seconds** including old plan byte goldens, strict
saved-head/input binding, unsafe-copy and non-v4 rejection. One overlapping
readonly-property assertion also passed after its Ruff correction. Whole Ruff and
mypy passed (1321 files), and diff check passed.

The design is frozen in `design/selected-plan-retained-proof-interface-v1.md`.
Current SQL witness capture, historical graph checks, archive/erasure tests,
collector/composer and actual v4 activation remain separate work. Opaque original
aggregate/map commitments are explicitly not reconstructed historical facts.
No provider calls, writes, hosted CI, push, merge, deployment or live qualification.
