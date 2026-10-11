# Selected/Traffic Same-Pass Read — 2026-10-11

Implements only the approved first slice of
[the reuse interface](design/creative-generation-validation-reuse-interface-v1.md).
The earlier five-second authority expiry's cause remains unproven. No deadline,
policy, source guarantee or retry behavior is changed.

Each retained proof invocation now loads its selected graph once and immediately
uses that exact graph for the private traffic body. The independent second fresh
proof invocation, before/after-image checks and complete retained witness capture
remain. No graph persists across passes. The private guard is entirely confined to
the factory invocation; only ordinary immutable pin/traffic values return, with no
Session, transaction or reusable authority token. Public traffic entry points still
load and validate their own selected graph and supplied pin.

The guard checks exact Session/root Connection/transaction identities and clean ORM
state, with explicit flush and transaction listeners. Swallowed flush or reentry
failures poison the invocation. All installed listeners are removed in finally,
including failure paths. No provider callback, image read or commit is introduced.

The existing receipt/sidecar race test's hook moved to the factored private traffic
body at the same semantic point: after the actual traffic read and before the next
fresh proof. Its original failure and no-gap assertions remain intact.

## Evidence

Durable directory: `/workspace/inlet-evidence/20261011/selected-traffic-pass/`.

- `guards.xml`:4 passed,0 skipped,1.906s. Flush, swallowed reentry, rollback and nested
  transaction events reject; later normal commit proves listeners detached.
- `sqlite.xml`:3 passed,0 skipped,7.165s. Actual range/selected HTTP fixtures prove
  exactly two selected-capture SQL reads for two retained passes, unchanged proof,
  and rejection of campaign change after selected read or lost present sidecar facts.
- `late-mutation-sqlite.xml`:2 passed,0 skipped,6.118s. Existing receipt/sidecar
  late mutation rejection preserved with the new private-body hook.
- `bothdb.xml`:30 passed,0 skipped,67.931s: new pass tests, existing selected
  retained viewer/absence/privacy/head/grant/session/role/campaign guards, and
  original late receipt/sidecar mutation cases on SQLite and PostgreSQL.
- `public-sqlite.xml`:1 passed,5.759s; expanded public loader performs its own third
  actual selected-capture SQL read and rejects copied invalid pin.
- `inactive.xml`:1 passed,2.122s; already-failed root transaction rejects before
  acquiring its connection. No invalid listener/token remains.
- `legacy-parity.xml`:2 passed,0 skipped,8.449s; both databases compare full proof
  against the exact former selected-read then standalone-traffic-read sequence.
  The optimized capture uses exactly two actual selected-capture SQL reads across
  independent passes; a subsequent public traffic call performs a third fresh read.
- Root separately measures final generation timing and normal API qualification;
  no claimed causal repair or supported-capacity timing theorem.
- Initial static checks identified import/test typing references; corrected directly.
  Whole Ruff and configured no-path mypy1405 subsequently passed. A final new-test
  nested-with style warning was fixed without behavior change. Final whole Ruff
  (`ruff-final4.log`), configured mypy1405 (`mypy-final4.log`) and diff check pass.
  Earlier static outputs and all XML/logs remain retained.
