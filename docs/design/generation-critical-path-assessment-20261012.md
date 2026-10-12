# Generation Critical Path Assessment

## Outcome And Release State

The first measured candidate, repeated retained-catalog decoding, is rejected as an
optimization package: its cost is too small to justify new proof machinery. No product
code, SQL query, migration, authority deadline or retention behavior changed in this
assessment. Migration 0094 and its qualified behavior remain intact. No additional
writer guards are justified by this measurement.

The evaluation target was a final generation save at or below two seconds on the
configured fixture, leaving three seconds under the unchanged five-second authority
window. This is a proposed engineering target, not a measured service guarantee. No
minimal dependency closure sufficient to reach it has been demonstrated.

HTTP release qualification remains 57 passed / 1 unresolved. Incident
INLET-REL-20261012-01 remains open. V3 remains default; V6/V7 remain release-unqualified.
This diagnostic grants no acceptance credit. All provider, credential, advertising,
spend, push, PR, hosted-CI, merge and deployment holds remain. Reconnect-retention policy
still awaits the owner decision. This is offline evidence, not live verification.

## Frozen Diagnostic And Actual Checks

Branch: `codex/inlet-w1-followup`; source HEAD:
`8fd4cfcf4fe7fc96ff0c6019a088631882345527`. Pending HTTP-admission changes were included
in the frozen source inventory but remain uncommitted and release-unqualified.

Evidence directory: `/workspace/inlet-evidence/20261012/generation-catalog-diagnostic01`.
Manifest SHA-256:
`3b33b9e3efd9fe47016671f86a3248ef22f91665251d64c8f66e74943f64878c`.
Observer SHA-256:
`539acfbcdb408f1da1c7adce30ac71ccdd65a759547bcb5a2a4ef625c3878da7`.
Runner SHA-256:
`2d23d5b38d218e1519b66a73c097f3fe8785777a5daa48f7d49b00dc98cf2c5e`.
Timing report SHA-256:
`19d0ea04cccdbf317f63d7198d235988a14c2c0e1afd6a63475cbde080ed9d00`.

One exact node ran, with the frozen bounded runner and evidence-only observer:

```
tests/test_google_budget_http_admission.py::test_assembled_http_observation_browser[postgres]
```

Original process exit 0; exact JUnit case passed; process duration 89.546056 seconds;
pytest reported 1 passed in 84.79 seconds. No interruption, kill escalation or remaining
process-group members. All 1,915 frozen source hashes and original Git state verified
before and after execution. No source changes occurred during the run. This was not
an unchanged acceptance retry and does not replace any original failed artifact.

Independent review found and closed observer defects before launch: SQL callbacks are
failure-contained; their stack is bounded; partial installation cleans up; listener
cleanup failures cannot prevent function restoration; report paths are unique and
rechecked before launch. Original preflight files are retained. Independent post-run
review verified the original result, exact XML identity, source integrity, cleanup and
complete 506-frame report. No observer error, truncation, incomplete restoration,
incomplete frame or expiry occurred.

The runner preserved launch memory headroom >= 1,536 MiB, runtime headroom >= 512 MiB,
workspace free >= 1 GiB, scratch free >= 2 GiB and a 900-second bound. Narrow launch
headroom does not establish production capacity. No Ruff/mypy/application regression
suite was rerun for this source-unchanged diagnostic; documentation receives a separate
whitespace check.

## Measured Attribution

All entries below are inclusive wall intervals within the same final save. Nested
rows must not be added. SQL counts are cursor executions observed in that scope, not
unique statements or an assertion of complete application-wide alias coverage.

| Scope | Calls | Wall seconds | Cursor executions |
| --- | ---: | ---: | ---: |
| Final save | 1 | 4.007920 | 2,385 |
| Final source checks | 1 | 2.240911 | 1,561 |
| Retained capture | 1 | 1.398327 | 774 |
| Catalog payload decode | 6 | 0.028940 | 0 |
| Owner evidence | 2 | 0.109646 | 8 |
| Selected reporting pin | 4 | 1.579564 | 1,156 |
| Selected graph | 12 | 0.916301 | 612 |
| Raw traffic graph | 2 | 0.361383 | 198 |
| Retained context construction | 2 | 0.081368 | 0 |
| Storage pair | 1 | 0.166189 | 0 |

The second owner-evidence call was 0.060610 seconds, including its fresh SQL and all
validation. Even removing that whole call would not materially approach the target;
removing it is not authorized or safe. The original candidate's complete dependencies
were PlanInputRow, InputCatalogReceiptRow, CatalogReceiptRow,
CatalogReceiptSelectionRow and exact in-memory document values. Its small measured
cost rejects introducing the proposed comparison proof now.

The disjoint outer selected-pin/selected-graph/raw-traffic spans total 2.104662 seconds,
including 0.724172 seconds of completed cursor SQL. The residual 1.380490 seconds
includes ORM fetching/materialization, guards, validation and observer overhead, not
just removable pure work. Even deleting that entire residual would leave about
2.627430 seconds of this observed save. Thus the available attribution does not support
a selected-decoder-only route to two seconds. It does not predict an actual optimized
runtime or prove a lower bound across different implementations/environments.

The earlier observer recorded a 2.568319-second save, but used different instrumentation
and ran under different conditions. Neither pass explains the earlier expiry's phase
or cause. Do not infer a performance regression or capacity guarantee by comparing them.

## Next Narrow Boundary And Decision

The smallest plausible next reconstruction boundary is
`campaign_performance.selected_storage.historical_capture`, whose complete data group
is:

1. SelectedCaptureRow: exact requested header and ownership.
2. SelectedFactRow: complete ordered membership, values and count/byte bounds.
3. Campaign: complete referenced campaign rows and their ownership/native mapping.
4. EventSelectionRow: exact referenced historical selection.
5. PerformanceCompletion: exact referenced aggregate completion and scope.

These share the owned historical capture/aggregate relation. A future pure decoder
would accept bounded immutable scalar snapshots obtained at the existing query
positions, not ORM models or caller-asserted freshness. Fresh row/membership comparison
must precede any validation reuse; changed or unsupported values follow the ordinary
validation/error path. No cached mutable value graph may escape. Preserve query order,
error precedence, original transaction and clean-session guards.

Leave `lock_scope`, current selection, `_aggregate`, source/private-grant comparisons,
privacy, authority, source checks around media, and all unrelated dynamic rereads
unchanged. This five-model group is a candidate for attribution, not an established
all-writer closure or an implemented optimization. Reusing pure validation after fresh
identical reads would not itself require 49 bespoke guard migrations. If a later design
removes dynamic reads, it needs separately proven ownership/membership writer closure,
including phantom insertion, update, deletion, old/new owners and parent cascades.

Recommended next package: expose and attribute this pure historical reconstruction
boundary while preserving SQL positions and failure ordering. Establish deterministic
reconstruction counts and a measured benefit before introducing reuse. Any eventual
optimization needs mutation/phantom/ownership/cascade regressions on both SQLite and
PostgreSQL, plus the actual configured workflow under a newly reviewed qualification
manifest. No additional diagnostic or optimization is launched by this assessment.

Do not mechanically guard the remaining 49 models or claim a sufficient reduced set
from inclusive timings. Broader query consolidation is an alternative to evaluate
explicitly; its lock order, snapshot consistency and failure semantics make it a
separate design, not an incidental decoder change.
