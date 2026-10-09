# Current Feedback Snapshot8 Repair

Approved interface `3ebc866`, implementation based on that commit. Scope is exactly
four functions/eight original failed SQLite/PostgreSQL identities in
`test_feedback_snapshot.py`. No directional-family tests or production code change.

The existing candidate-receipt producer still executes its genuine original Google
45,000,000-micro action under literal historical PIN2155, returning only strict
scalar identities. Current code reuses the unchanged `load_receipt_candidate`
owned-source/receipt reconstruction. The source lifecycle is extracted into
`retained_receipt_source`; the original reconciliation fixture retains its exact
`reconciled` finalizer, without an unchanged-or-reconciled union. The new snapshot
fixture instead requires exact immutable provider history and zero current mock
writes. Its only scoped replacement is the snapshot test module's local setup
alias, validated once per test with the exact engine/configuration and receipt
mode; no global fixture or capability guard is replaced.

The current `prepare`, original second commerce publication, owned snapshot,
explicitly synthetic effective-time/numeric facts, persist/read/replay/retraction,
zero-signal, actual session and source corruption checks remain unchanged. The
per-test commerce read setting is the original source setup value. These tests
are synthetic assessment-policy evidence, not live qualification or causal proof.

## Protected History

`protected-tables.json` records the exact 24-table set: every current `provider_`
table plus the approved historical spending/draft/media tables. All rows/columns
are compared in primary-key order before and after current work:

- customer_campaign_drafts, customer_campaign_revisions, customer_media_objects;
- mandate_actions, mandate_audits;
- provider_automatic_decisions, provider_execution_approvals,
  provider_execution_attempts, provider_execution_consents,
  provider_execution_mandates, provider_execution_receipts,
  provider_execution_responses, provider_execution_reviews,
  provider_execution_revisions, provider_execution_runs, provider_execution_steps;
- provider_exposure_reservations, provider_period_ledgers, provider_qualifications,
  provider_reservation_replacements, provider_review_approvals, provider_reviews;
- spending_mandate_revisions, spending_mandates.

Actual attempt/receipt/action/held-state validation remains in the source context;
the new wrapper also verifies all four effect rows belong to the owned workspace.
Commerce/assessment/feedback/privacy derivatives may change under the original
current code. The test's temporary plan-digest corruption is restored; outstanding
transactions close before final history equality. Session revocation is outside
provider history. No persistent provider change is permitted in this wrapper.

The shared child now validates a plain SQLite URL with no query and an existing
regular nonsymlink file resolving exactly to output.parent/current.sqlite before
engine creation. Parent checks all initial tables empty (except Alembic); existing
child check remains. Disposable-loopback PostgreSQL, UUID schema, exact current
engine, source lifetime and bounded scalar/child process contracts are preserved.

## Evidence

Artifacts: `/workspace/inlet-evidence/20261009/feedback-snapshot8/`.
`verify_ast.py`/`ast-proof.json` compares the entire snapshot module after only
normalizing the added fixture argument, local engine assignment, marker and
fixture import: identical. Shared `prepare` and nested synthetic expressions are
therefore unchanged. Existing receipt loader, effects snapshot and reconciled
finalizer are independently AST-identical.

`probe.log/xml`: **7 passed**, 21.86s — five no-engine-call SQLite target negatives
and one actual positive snapshot case on both databases. These overlap the final
cohort; no additive closure credit. No failed probe in this package.

Final cohort and static results are appended after completion. No Full/aggregate,
external provider, hosted run or advertising capability change. The original
aggregate remains failed; only exact matched original identities may receive
closure credit after independent review.

## Final Results

`qualified.log/xml`: **117 passed, zero skipped/errors/failures, 86.545s** JUnit
(pytest86.55s). Exact composition: snapshot8, unchanged receipt-reconciliation2,
current execution boundaries35, current transport boundaries51, SourceLifetime16,
and SQLite target guards5. `verify_coverage.py`/`coverage.json` proves exact equality
of the eight passed snapshot `(classname,name)` identities with the eight original
frozen failed identities; no overlapping probe/shared tests inflate credit.

Whole Ruff initially exposed an inherited E501 in
`candidate_review_link_retained_fixture.py:109`, outside this package. `ruff.log`
preserves the failure. Parent authorized applying its already-reviewed `e61d553`
formatting-only line wrap. That exact patch is included separately in this
successor; no related test repeat was needed. Final `ruff check .` passed
(`ruff-final.log`); bare `mypy` passed **1192 source files** (`mypy-final.log`);
`git diff --check` passed (`diff-final.log`). Each terminal output was inspected,
not inferred from a later command's exit. The normalized AST proof still passes.

Runs used `/workspace/inlet-venv/bin` in `/workspace/inlet-feedback-snapshot8`,
authorized loopback database `inlet_oct07_next_integration_ci`, disposable=true,
and fixture-owned isolated schemas; no resets. Final pytest selected exactly
`test_feedback_snapshot.py`,
`test_optimization_candidates.py::test_receipt_append_erases_derived_only`,
`test_planning_execution_boundary.py`, `test_planning_provider_transport_boundary.py`,
`test_producer_source_lifetime.py`, `test_feedback_snapshot_fixture_guard.py`.

Available source scalar/log/lifetime records are copied under `producer-records`
with original paths in its `origins.json`. This is artifact preservation, not
additional test coverage. No original media/SQLite/raw test artifacts were removed.
Independent review remains required before integration. Directional8/adapter6
remain outside this implementation and require their separate interfaces.
