# Current Reported Rule Dependencies And Worker Source

Proposal only; base8880a29. No implementation, test execution or new closure credit.
The original failed-node ledger identifies exactly18 current cases, not historical
forward execution. Implementation requires shared-interface review.

## Exact Scope And Classification

| Module / function | Original parameters | Count | Current behavior to retain |
| --- | --- | --- | --- |
| test_reported_rule_dependencies / test_dependency_erasure_preserves_original_obligations | SQLite/PostgreSQL × candidate, comparison, capsule, supersede | 8 | Actual0083 downgrade refusal, derived dependency cascade, superseding request, unchanged original held obligation |
| test_reported_rule_dependencies / test_foreign_dependency_rejected | SQLite/PostgreSQL | 2 | Actual scoped DB constraint failure, rollback preserves candidate job |
| test_reported_rule_worker / test_owned_reported_queue_produces_separate_decision | SQLite/PostgreSQL × none, session, source, capsule | 8 | Actual current enqueue/read worker, source/session changes during native GET, suggested decision/export, idempotent not_due |

The pure registry test in the dependency module is unchanged and is compatibility,
not an additional frozen failure. No retained_execution decorators on these cases.
No changes to reported automatic/admission/API tests or other shared callers.

The worker does NOT start an automatic advertising execution run. Its actual path
is CandidateRuntime → enqueue_candidate_selection/enqueue → service.process →
process_reported_result → read_reported_rule/compile_reported_rule/current-source
recheck → CandidateResult. Native IO is a current Meta read. There is no executor
runtime needed by these three functions. Original assertions explicitly require
no additional attempts/reservations/posts and spending_authority='none'. Therefore
worker8 can share the read-only source, with a separate bounded qualification step;
there is no justification for retiring it or introducing automatic Start authority.

## Current Failure Chain And Reuse

ready_reported_rule currently wraps reported_feedback_fixture.ready to optionally
capture result[6] (execution runtime), then calls acquisition_fixture → seeded →
original durable ready/prepare/approve/create/claim/execute. That source setup is
incompatible with the current write boundary. Neither selected caller supplies
execution_out. The rest of ready_reported_rule performs current report acquisitions,
comparison/native GET, real commerce publication and typed work/observation assembly.

Reuse the already approved relative original source:
retained_reported_planning_relative_fixture(engine, artifacts,
expectation=ExpectedPlanningConfirmation()). Leave expectation UNBOUND: its existing
finalizer then requires the entire provider/mandate-action graph unchanged and no
new planning preparation/consent. No planning consent or new mandate is needed.
The closed child uses its existing actual relative original effect timeline and
returns RetainedReportedOriginalIds only. Its original45m receipt is genuine;
no ready reports, comparison, candidate result or runtime is imported.

Use the existing reported_original_fixture.customer_engine for actual owned SQLite
file/isolated PostgreSQL, with base_customer_engine explicitly imported as in other
approved consumers. Add a new small source wrapper that validates artifact parent
paths before invoking the existing source helper and records schema_snapshot before
and after, without changing shared producer semantics. Existing child PIN, scalar
shape, URL validation, SourceLifetime profile and timeout stay unchanged.

Relative source dates are selected before the original effect and keep actual goal
and mandate current for the report window; they replace obsolete absolute fixture
dates, not persisted timestamps after the fact. Do not redate a receipt, renew its
session, change a goal or manufacture reports to obtain the expected decision.
If genuine current goal assessment or policy lifetime fails, stop and report it.

## Shared Current Assembly Interface

Proposed new tests/reported_rule_current_fixture.py:

- `reported_rule_original(customer_engine, tmp_path) -> Iterator[RetainedReportedOriginalIds]`:
  invoke the unchanged relative source with unbound expectation; require default
  write denial throughout; snapshot physical schema and preserve original graph.
- `ready_current_reported_rule(db, config, path, monkeypatch, *, original: RetainedReportedOriginalIds) -> tuple[Any, ...]`:
  same seven return positions as ready_reported_rule, no execution_out parameter.
  Validate db uses the actual owned fixture engine. Call prepare_reported_read for
  exact owned receipt/session/source/goal, then prepare_reported_acquisition for
  actual bounded GET imports and original actor/session continuity.
- Extract `_reported_rule_from_acquisition(db, config, data) -> tuple[Any, ...]` in
  reported_rule_fixture.py. `data` is the existing eleven-position acquisition tuple
  (wid, principal, runtime, job, request, source, clock, runner, requests, control,
  native server). Move the entire original body from
  `control.update(before_conversions='2', after_conversions='4')` to return,
  AST-identically. Existing ready_reported_rule preparation/signature and
  execution_out recording remain unchanged and call this extracted tail.

The new wrapper assembles that same acquisition tuple from actual current helpers
and a NEW current `Server('meta_ads')`. Validate original owned OptimizationReceipt,
request, account123/campaign5, operation meta daily budget45m and USD exponent2;
only then initialize the server's native campaign daily_budget='4500'. This models
current GET response state, not a new receipt or mutation. server.posts starts and
remains empty; do not prepopulate the historical POST count. Current
MetaOptimizationTransport parses actual MockHTTP in the unchanged tail and worker.
No historical runtime, callbacks or test-ready object crosses into current code.
The unchanged tail retains 3 complete calls, +61s, then2 calls, before2/after4
conversions, and exactly4 completed reported observations in the resulting view.
Set config.shopify_measurement_enabled=True explicitly before the actual current
FakeMeasurement page, matching the source setup's prior configuration effect and
existing approved current acquisition helpers. Do not seed publication rows.

At selected consumer setup only, invoke the new wrapper with the original scalar
fixture. Preserve every original parameter decorator, assertion, rejection block,
post-setup body and current runtime callback. The actual engine is explicit through
fixture imports, never ignored in favor of a hidden different database.

## Allowed Current Work And Immutable History

The existing relative source finalizer snapshots every provider_* table and
mandate_actions. All original rows/columns must remain identical; no new effect,
review/approval/run/step/attempt/response/receipt/reservation, mandate/consent or
ledger mutation is allowed. Physical schema is identical at exit.

Current acquisition may create its actual Meta staging/import/performance/report
jobs/slots/capsules/comparison and the real commerce publication/watermark. Candidate
selection/enqueue/processing may create only its normal derived candidate graph.
These are actual services, not a generic mutation callback or seeded expected data.
Dependency negative paths retain their exact CandidateJob/comparison/capsule deletes
or superseding comparison, with genuine cascade and0083 downgrade refusal. Foreign
scope insertion still fails its actual DB constraint and rolls back. Worker adverse
paths preserve their current mid-GET session.revoked_at change, CommerceStore.revision
increment or capsule deletion. They are not financial-history exemptions.
The existing original assertions and final immutable graph must both pass.

## Bounded Qualification Order

1. BothDB positive source/read probes: dependency foreign test and worker none path;
   prove actual owned goal confirmed and mandate live before worker claim.
2. Dependency10 plus unchanged registry test; exact frozen identities/AST proof.
3. Worker8, all original GET-time source/session/capsule races and view/export fields;
   preserve proposed44_750_000, reported CPA5_000_000→2_500_000, one original and four
   completion counts, no causal lift/no spending authority. Stop if any genuine
   current semantic contradiction appears; do not broaden runtime or permissions.
4. 86 current boundaries plus bounded existing relative-source/current-acquisition
   compatibility because the extracted tail remains a shared old caller seam.
   No automatic execution cohort, new Full or whole historical batch.
5. Whole Ruff, bare mypy/diff, exact identity intersection and raw failures retained.

Dependency10 and worker8 should be reported separately even if one source package
is reviewed together. No full-case quality or live qualification claim follows from
these fixture repairs. This read-only investigation ran no tests/providers/DB work.

## Proposed Current Fixture Scheduling Refinement

Qualification found two PostgreSQL setup failures: the first three-completion loop
received up_to_date before any worker assertion. Six worker cases passed; failure
rows were not retained after normal isolated-schema teardown. One authorized
instrumented PG-session diagnostic passed13.99s, but observed a concrete divergence:
fixed completion page9 supplied/runtime05:22:07.368057, committed job next_due_at
05:22:07.383220, separate DB read05:22:07.468385. Its original +61s then allowed the
next page. No failed-page timing was measured; association with the two failures is
supported by due_job filtering against supplied now before effective_now and by
capture_terminal_window assigning the effective DB/app completion timestamp.

Proposed current-only correction, pending review: wrap this one acquired runner's
page method for the duration of current assembly, always delegate once to the actual
method and return its exact result. For successful fixed completions, read the exact
owned job and latest matching job capsule in a separate current Session; require
completion count advancement and next_due_at equal that capsule's actual completed
at. Advance only the fixture's clock list to max(existing, committed completion).
Subsequent page calls use max(explicit supplied now, fixture clock). Never move a DB
row/timestamp, retry an up_to_date result, extend expiry, jump to an arbitrary future
schedule, or change the original +61s spacing/tail. Rolling completions do not move
that clock from a merely pending job. Original shared ready_reported_rule is untouched.

A bounded actual delayed fixed-report probe should demonstrate that the observed
completion can overtake supplied time and the next original read still uses the
actual due frontier. Preserve the earlier6pass/2fail and diagnosticpass independently;
rerun affected current dependencies/workers plus approved compatibility after repair.

Approved timestamp refinement after the first adapter probe: completion and capture
are distinct real timestamps. PerformanceCompletion.completed_at binds
capsule.acquisition_completed_at; capture_terminal_window samples effective_now
again for capsule.captured_at and job.next_due_at. Validate both typed/scalar pairs,
completion <= capture and exact capture == job.next_due_at; follow only that
actual committed capture timestamp. No arbitrary scheduling field becomes clock
authority. The initial overly strict equality failure is preserved as fixture
qualification evidence, not weakened source integrity.
