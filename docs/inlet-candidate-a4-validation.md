# Frozen a4 Validation And Successor Repairs

Frozen candidate: `a4fcd3a35d585d11def78261382234e081fb8f6b`, tree
`67f18fa0b05ae6ce5637f73591cba66774f5928d`, draft PR130. This artifact
remains unchanged. Successor package results do not turn its failures into passes.

## Observed Results

Local Full completed with **exit1** on 2026-10-06, verified10:55UTC: **5 failed,
3390 passed,67 skipped**,129 warnings in5059.83s. Failures are the four cases below
plus their nested-Full wrapper; no additional cause appeared. Full stopped at pytest,
so subsequent static/security/privacy/migration gates did not run in this invocation.
Hosted run37443239927/job112201796837 completed **failure**:5 failed,3396 passed,
61 skipped,129 warnings in5132.55s. Nested4 failed,3396 passed,62 skipped. Same
four causes plus wrapper; later validation gates were skipped. Actual checkout
92a1590238c9e37acd994fcec5f491342aa1025f has the exact frozen a4 tree. Saved full
log `/tmp/inlet-pr130-a4-hosted.log`; artifact11407171330 (1729bytes), SHA256
a5cabc9b50932cc1825818eaa33a1e340ddb4e85a376b36b56925b50a42c6298,
expires2026-10-13.
Local log: `/tmp/inlet-oct06-candidate3-full.log`; actual wrapper exit code:
`/tmp/inlet-oct06-candidate3-full.exitcode`.

The first bounded nested Full invocation completed with **3386 passed,72 skipped,
4 failed**,3462 collected tests,2456.159 seconds. Preserved report:
`/tmp/inlet-a4fcd3a-nested-full-0.xml`. Both positive-conversion regression cases
and both Meta customer browser cases passed in this invocation. The outer test
will report its nested failure separately; do not add or predict final totals.

| Failure | Cause | Exact successor repair and verification |
| --- | --- | --- |
| `test_repurchase_requires_terminal_old_subscription_and_owned_completed_session[sqlite]` | A replacement event was classified as a historical subscription before resolving its locally owned checkout | `26235936dd257f7873b1826c157c9403a627b211` / PR215 resolves the owned checkout first, then still requires the prior subscription to be terminal and the replacement to pass payment/offer qualification. Root billing/transport/original-regression suite70 passed. |
| Same test `[postgres]` | Same ordering defect | Same repair; PostgreSQL case included in70-pass result. Foreign/open/unpaid replacements remain denied. |
| `test_replacement_migration_preserves_populated_obligations` | The historical0058 fixture invoked a current producer whose later0066 completion table cannot exist at0058 | `9e8d9f5018fb1098bca8b9800fd8f97ecf62990f` adds `without_google_capture` to the explicitly historical fixture helper only. Current-schema capture is unchanged. Root historical/current/native-restore combined suite8 passed,1 SQLite migration skip; complete0073 migration roundtrip passed on a separate disposable database. |
| `test_default_runtime_is_unavailable` | The old usable-factory assertion supplied only a key/version despite the new mandatory reviewed merchant/offer configuration | `26235936dd257f7873b1826c157c9403a627b211` preserves unavailable behavior for incomplete configuration and supplies the required configuration to the usable-factory case. Included in70-pass suite. |

Relevant logs: `/tmp/inlet-next-billing-repurchase.log`,
`/tmp/inlet-next-0073-join.log`, `/tmp/inlet-next-0073-roundtrip.log`.
No application missing-table fallback, weakened billing gate, skipped regression,
manual workflow dispatch, merge or deployment is part of these repairs.

## Successor Assembly

`c6d72b6b9d1560dbfd5c861ce315c4352d6564d1` combines these repairs with session
control, directional consumer,0073 migration join and concrete read-only diagnostics.
Diagnostics backend246 passed; actual browser/API/vault/collector UI16 passed with
synthetic transport across all three providers and both databases. Ruff/mypy617,
JavaScript syntax and whitespace passed. This is the prepared successor code,
not yet a newly qualified Full/hosted artifact.

Original acceptance remains unchanged while the owner considers PR214. A universal
guarantee against every external account edit is distinct from Inlet's obligation
to keep its own actions within the approved mandate. Restricted provider/account
profiles are being assessed for enforceable behavior; unsupported universal promises
must not be added to the audit, and unqualified financial facts must not be invented.
The pending product decision does not authorize recommendation-only acceptance or
public claims, nor changing existing runtime gates.

## Repaired Validation Snapshot

Frozen successor `dc3c0d5b63eee06bd04a0aa73354ae289ef55333`, tree
`5d17ce391d0b1b8c384cb374ad3ebd7ddda6c0d0`, is pushed on
`codex/inlet-mvp-validation-next`. Local Full started10:54UTC in its independent
checkout and disposable `inlet_oct06_candidate4_ci` database. Log:
`/tmp/inlet-oct06-candidate4-full.log`; eventual exit-code companion. No pass claimed.
After retaining both a4 terminal results, PR130 advanced to dc3c0d5. Its normal
CI run37453370292/job112234984790 failed before starting any runner step (10:59:01
to10:59:04UTC). No job log exists (404). Cause is unconfirmed: the connector rejects
the check-runs annotation endpoint as unsupported. No GitHub usage/resource limit
has been established; do not infer one from empty steps or an endpoint error.
No rerun or manual dispatch was attempted. Parent must inspect the failure
annotation to distinguish usage/resource/account limits from another startup issue. New0074 campaign
performance and Google total-budget backend/UI are later development and deliberately
not part of this frozen snapshot. No manual dispatch, merge or deployment.
