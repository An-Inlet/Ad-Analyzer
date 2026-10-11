# Owner Domain Checked Kernels

Implementation of reviewed5a8f6c0. Scope two owner-contract modules plus
new pure tests. Public witness digest, public review/proof wrap serializers and Frozen
are unchanged. Existing full model validations remain at every external entry and
fresh SQL pass. Private checked derivations are used only after same-invocation strict
validation with exact concrete model/field inventory and nested declared-type checks;
otherwise original public fallback remains. No generic cache or trusted prepared token.

`resolve_google_daily_budget_intent` avoids validating its already checked witness
again through public digest/facts calls. Review after-validator uses checked resolver
and action derivation only for eligible exact children. Proof complete-validator's
byte bound projects its already validated exact child fields without invoking child
wrap revalidation; public serializer handlers and all their options remain untouched.
The third-file proof comparison proposal is deferred.

Evidence: `/workspace/inlet-evidence/20261011/owner-domain-kernels/`.
Before production edits, source5a8f6c0 generated five local immutable golden artifacts:
complete/zero/empty proof and ordinary/removed witness. baseline.json contains source
hashes, exact output hashes and digests/facts. baseline_reproduction.py records the
exact fixture parameters. This authorized fixture capture was not a pytest run and
made no provider/SQL calls. No prechange multiple-owner fullproof golden was captured;
that coverage must not be claimed from these five artifacts.

Initial whole mypy01 found a test import of a non-reexported compose alias; changed to
the defining module. Initial style output is retained. Final whole Ruff and configured no-path mypy passed1479 files (`ruff-final.log`,
`mypy-final.log`). Source and test preflight were independently closed before execution.
No latency margin or incident closure is asserted.


The exact authorized seven-file pure cohort collected194 nodes (`nodes01.log` and
`selection.json`), with source hashes/output absence/cgroup memory/workspace/scratch
floors recorded. No other pytest/mypy process was active before launch. The single
`pure01` run passed all194, zero skips/errors/failures, in11.847seconds, exit0. No retry
or source change followed. This includes existing two-independent-owner binding and
V4/V5 full-document golden regressions; the five prechange artifact set remains the
only newly captured golden set, with no additional multiple-owner fullproof baseline.

The new tests cover exact baseline bytes/digests, repeated-call full witness validation
and facts derivation counts, copied unsafe public boundaries, public serialization
options, custom subtype/extra-field fallbacks and exact proof UTF-8 B/B-1 size limits.
No API/SQL/runtime timing qualification was run. Final `git diff --check` passed.
`manifest.json` binds final source and all retained evidence including initial static
failure logs; `frozen-head.txt` records the local source commit.
