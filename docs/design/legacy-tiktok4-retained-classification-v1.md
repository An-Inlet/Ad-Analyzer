# Legacy TikTok Creation Policy — Four Retained Engine Contracts

Proposal only on f7d131c. Exact function:
`test_tiktok_legacy_creation_policy::test_legacy_forward_creation_stops_without_erasing_original_history`,
SQLite/PostgreSQL × emitted false/true =4 original failed identities.

This is an existing direct coordinator policy regression. It deliberately creates
one pre-policy claim (and optionally one actual MockHTTP unknown result), disables
only the old `new_creation_allowed` predicate within that historical setup, then
requires five forward coordinator operations to reject with the exact old TikTok
policy reason. Finally it parses original evidence, reconciles the original attempt,
asserts no replay/provider POST increase, one attempt and unchanged held reservation.
The new planning artifact denies all forward writes earlier, making this retained
policy regression unreachable unless its explicit historical engine capability is
scoped to this one test. It has no customer API/session/browser/privacy/DDL consumer.

Proposed change: add only per-function `retained_execution` and
`usefixtures("retained_execution_engine")` decorators, as already reviewed for other
direct retained coordinator contracts. Do not change the function signature, body,
assertions, existing emitted parameters, helper, production code or original policy
monkeypatch lifetime. The read/reconcile assertions remain part of that direct engine
regression; do not label it current default-artifact read qualification.

Current planning capability remains covered separately with unchanged86 execution
and transport boundary cases and4 capability cases, including all five coordinator
forward methods and TikTok HTTP mutators. The retained fixture is forbidden by
collection guards on planning_boundary cases. No module-wide marker, extra historical
manifest, current source helper, restored route or capability change.

Qualification: exact4 plus unchanged86+4 in one bounded run, assertion/full-body AST
proof excluding only the two added decorators; whole Ruff/bare mypy/diff with separate
exits. Explicit unique basetemp and logs/XML; MockHTTP only, no live operations.
If the original old-policy assertions still fail, preserve evidence and review the
concrete cause rather than weaken them. Independent classification review first.
