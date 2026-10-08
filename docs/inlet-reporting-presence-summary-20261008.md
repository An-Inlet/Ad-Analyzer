# Pure Campaign Presence Aggregation

New private helper `summarize_presence` consumes the complete typed header/fact set,
revalidates its exact digest/scope and local/native campaign mapping, then derives
immutable campaign aggregates. Cell absence and absent calendar days remain separate.
Empty or partial observations never become a full-window selected-conversion zero.
Only explicit selected-event presence on every requested day, closed/full requested
interval and complete pagination can qualify the observed-window zero flag. Unknown
attribution remains unknown and no causal or spending claim is introduced.

The100click/10conversion/$100 example remains positive. Money stays arbitrary exact
integer during sums; Decimal conversion sums use an explicit50digit Context rather
than inheriting caller precision/exponent/traps. No API, planner, importer or SQL
consumer is wired by this package; construction is not ownership proof or a V3 report.

Initial12purecases passed0.105s. Independent review found P2: precision-only context
still inherited exponent/trap settings. Repaired with explicit Context and tests for
lowEmax with Overflow traps enabled and disabled. One transient missing-colon edit
failed syntax/collection and is not counted as a pass. Final **14passed0.101s,0skips**;
wholeRuff/mypy1073/diffchecks passed. Evidence:
`/workspace/inlet-evidence/20261008/presence-summary-context-repaired.{log,xml}`.
Review closure/final integrated commit pending. No Full/live/remote action.
