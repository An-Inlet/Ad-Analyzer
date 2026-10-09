# Durable Reported Planning Regression: Relative Original Source

Proposal for root review; no producer or consumer implementation in this commit.
Successor to the explicitly dated `cc02905`/`65f5deb` service/HTTP evidence.
The fixed October producer and diagnostic probes remain unchanged and non-default.

## Why A Fixed Test Clock Is Insufficient

`initial_planning.clock.effective_now(db, runtime)` takes the maximum of the supplied
application clock and `lifecycle.privacy.database_utc_now(db)`. The latter executes
actual PostgreSQL clock_timestamp / SQLite strftime. `reported_feedback.current_report`
also samples this actual clock. Customer access independently uses time.time.
A fixed October application clock will eventually expire otherwise valid evidence;
replacing these guards or DB clocks would not prove the current contract.

Use a relative source-before-effect calendar instead. Only synthetic source input
and the pinned historical producer's already-supported explicit service clocks are
relative. Current DB, identity, login, access and final authority clocks stay real.
No dated assertion, skip, xfail, TTL extension, global clock patch, post-effect date
rewrite or fabricated ready capsule is allowed in the durable lane.

## Closed Timeline And Producer Interface

New closed profile `reported_planning_relative_original`, driver
`tests/fixtures/retired_execution/reported_planning_relative_seed_driver.py`, and
fixture `tests/reported_planning_relative_fixture.py`. Do not change either existing
original producer or its fixed-period behavior. Reuse unchanged strict empty-DB,
disposable URL/schema, bounded output and SourceLifetime rules. No arbitrary import,
callback, configurable timestamp, goal or financial policy subprocess interface.

The child captures `as_of = datetime.now(UTC)` once before source construction.
A pure private frozen `RelativePlanningTimeline.from_as_of(as_of)` derives:

- `effect_at`: UTC noon on the date 15 days before as_of's UTC date.
- `baseline_start/end`: the full calendar month immediately before effect_at's month;
  synthetic order/agreement occurred at UTC noon on that month's 10th day.
- `target_start/end`: first day of the month after as_of's month through the following
  month's first day; deadline target_end minus one day.
- `budget_start`: first day of effect_at's month; `budget_end`: target_end.
  The original provider policy and confirmed goal use these identical boundaries
  before any optimization effect. This leaves a full future month of headroom,
  including month/year rollover, rather than failing during the last minute of a month.

Pure timeline tests cover month starts/ends, leap February, December/January and
assert baseline closed at confirmation, effect inside budget, after-report window
closed before as_of, and as_of plus the existing 63-second repeat acquisition within
budget. These are synthetic test inputs, not customer recommendation defaults.

The context manager yields the unchanged `(Engine, RetainedReportedOriginalIds)`;
`ExpectedPlanningConfirmation` remains required, exact and unchanged. Return no
historical runtime, authority object or usable cookie. A bounded diagnostic timeline
JSON may be retained alongside IDs, but consumers derive and verify authoritative
periods from actual persisted goal/policy/receipt, never that diagnostic file.

## Actual Source Construction Before The Effect

Do not call fixed-date `test_commerce_measurement.setup/source` or
`test_customer_goals.definition`: those embed October/September/November literals,
including default arguments that changing a module NOW would not repair.

Construct the synthetic owned workspace and current-schema source using the same
explicit fixture-level owned connection/vault pattern, with credentials minted at
`effect_at` and explicit measurement scopes, USD/UTC metadata and native ownership.
Bind with actual `bind_shopify` / `bind_store`. Complete an actual
`CommerceSyncService.page(now=effect_at)` using FakeMeasurement with an explicit
relative order body and agreement (`99` gross, `9` tax), so the source history and
baseline come from the real terminal importer, not hand-assigned coverage or a
fabricated snapshot. An absent/invalid baseline stops the probe; do not weaken it.

Build exact GoalDefinition using those derived windows, unchanged100m target,
50m budget and balanced input. Actual revise/preview/confirm at effect_at must pass.
Then construct original same-period provider policy with unchanged100m total,
80m per-plan,20m positive cap, and the same actual Meta target. Through untouched
pinned services: native50m read, optimization prepare/approve/run/claim, one MockHTTP
50m→45m mutation, authentic response/receipt/40m hold. No legacy campaign-draft
references are introduced. Keep original lineage assertions and exact financial
snapshot; every goal/ledger/date existed coherently before the effect.

The historical source's existing60-day fixture session remains provenance of that
fixture only. Durable HTTP coverage logs in normally with real current time and
ordinary TTL; the source dummy session is not a cookie. No source grant is stretched:
current commerce refresh uses actual token-refresh logic/FakeMeasurement just as
existing acquisition does. Failure at a real freshness/retention/period guard is
reported before further consumer adaptation.

## Current Consumer And Clock Boundaries

`prepare_reported_read` may reuse its existing real current clock and scalar lineage
checks. Actual request_comparison derives both seven-day windows from the genuine
receipt; with effect15 days ago its computed after-window close is already past.
Assert next_due_at is request-time due, not a future date requiring renewed authority.
The actual current acquisition helper still obtains real jobs/checkpoints/capsules,
observes all original scopes, and advances only its established1+61+1 seconds for
repeat spacing. No row timestamps or acquired data are rewritten. The current DB
floor and ordinary session expiry remain enforced. Capturing the real starting
clock is not freezing the database or suppressing final fresh checks.

For HTTP, actual normal login, actual comparison POST/GET, initial V2 POST and feedback
POST use the already-reviewed current-session handoff. Since the reporting window
is already closed, no simulated issuance/access time seam is needed. Initial runtime
source clock still expresses the existing bounded acquisition cadence; label that
explicitly. Do not claim this eliminates every synthetic clock in test fixtures.

Current baseline preparation uses actual acquired profile/native catalog, real
PlanningConsent, and the goal's genuine period. Reuse existing ledger exactly; no
new ledger, execution consent, current effect or financial mutation. Initial46m and
feedback47m, cap/quantum checks, original MockHTTP POST count1 and current GET-only
assertions remain unchanged.

## Ordered Qualification And Consumer Gate

1. Default-collected two-DB relative producer→actual acquisition→planning confirmation
   probe. Assert exact same ledger, no execution consent on new draft reference,
   current confirmed goal and actual immutable chain. Preserve failure traces.
2. Durable default-collected service and normal real-time HTTP valid/adverse regression
   for the checked_planning_limits production fix. This replaces no dated evidence;
   it provides the missing lasting regression. At least current session revocation,
   stale planning policy, exact caps/quantum and zero-slot rollback remain explicit.
3. After review, adapt remaining28 current consumers using the same source and local
   genuine planning-baseline helper. Preserve each original assertion and two existing
   SQLite concurrency skips; classify any goal-period-dependent assertion separately.
   Graph-deletion tests require an exact reviewed expectation, not generic allowlists.
4. Existing fixed producer/one old acquisition caller plus strict default guard tests
   remain compatibility checks. Required whole Ruff/bare mypy/diff per package.

This proposal closes the fixed-date feasibility question without claiming the new
relative producer already passes. First actual both-DB probe must be reviewed before
moving the28 consumer bodies. No Full, hosted/native call or execution-policy change.

## Reviewed SQLite File Ownership Tightening

The relative parent accepts only a plain `sqlite` URL with no query, host/user/port
components, naming the absolute existing regular nonsymlink file
`artifacts.parent / 'current.sqlite'` supplied by reported_original.customer_engine.
Reject alternate files, relative paths, driver variants and symlink aliases before
any database access or child launch. The child independently enforces the same
rule against `Path(output).parent.parent / 'current.sqlite'` before create_engine.
No source/target database creation or fallback is allowed. PostgreSQL ownership
checks remain unchanged. Negative tests exercise both actual entry boundaries with
foreign/query/missing/symlink inputs and a forbidden database factory/access sentinel.
This applies only to the new relative fixture; existing fixed producers stay intact.
