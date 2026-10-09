# Relative Reported Planning Source — Stage 1

Branch `codex/inlet-reported-planning-relative`, base `fe1e91d`.
Implements the reviewed relative-source interface, default-collected first-stage
probe and pure calendar checks. No production code, fixed producer, existing
ExpectedPlanningConfirmation or remaining28 consumer changes.

The new closed SourceLifetime profile `reported_planning_relative_original` runs
against the unchanged historical PIN. It constructs USD/UTC commerce source inputs
and a relative order before a real terminal commerce import, confirms the actual
goal, then creates the original same-period policy/ledger before the actual pinned
optimization prepare/approve/run/claim/MockHTTP effect. One native50m→45m POST,
authentic receipt/40m hold, original caps100m/80m/20m and goal budget50m remain.
No original row dates, ledger, receipt or authority are modified afterward.

The child captures current UTC once. Effect is15days earlier, prior complete-month
baseline, target next full month, identical goal/provider budget period from the
effect month's start through target end. Real DB/auth clocks remain unchanged.
The original fixture's60-day scalar session is preserved fixture provenance; this
package does not yet claim ordinary-login HTTP qualification on the relative source.

Current-schema probe performs actual comparison/acquisition, proves request due is
already past, verifies retained lineage and confirmation-before-effect, then runs the
actual current commerce refresh, calibration/native catalog and planning preparation/
confirmation. Before refresh the historical commerce frontier is correctly unavailable;
after refresh it is confirmed with90m actual baseline. New draft reuses the exact
original ledger with no new execution consent. Unchanged strict outer graph checks
all original financial rows and only the approved exact planning draft/confirmation.
Current native calls are GET only. Only scalar IDs cross the child boundary.

## Exact Evidence

Directory: `/workspace/inlet-evidence/20261009/reported-planning-relative/`.
Both-DB commands use the existing disposable localhost PostgreSQL URL/flag and
isolated schemas; no aggregate database or shared target reset.

- Initial SQLite `pytest -q tests/test_reported_planning_relative.py -k sqlite`:
  1failure9.942s (`first.log/xml`). New fixture omitted required Workspace.client_name,
  rejected before source/effect. Added required synthetic value.
- Same SQLite probe:1passed9.864s (`second.log/xml`).
- `pytest -q tests/test_reported_planning_relative.py tests/test_reported_planning_relative_calendar.py tests/test_reported_planning_original_guard.py tests/test_producer_source_lifetime.py`:
  28passed/2failed21.631s (`qualified.log/xml`). The two new chronology assertions
  incorrectly expected confirmed baseline before the real current commerce refresh.
  They now explicitly prove unavailable before refresh and confirmed after it; no
  production/clock/source field changed. The28 passing cases comprise10 calendar,
  2 unchanged strict guard and16 SourceLifetime checks.
- Final affected `pytest -q tests/test_reported_planning_relative.py`:
  2passed24.768s, both databases, no skips (`final.log/xml`, `final-artifacts`).
- Whole `ruff check .`, bare `mypy`: pass,1,185files (`ruff-final.log`, `mypy-final.log`).
- `git diff --check`: pass. New scripts/test paths included in static checks.

All producer logs, scalar IDs, test databases and SourceLifetime manifests remain
under evidence basetemps; verified immutable extracts were removed by SourceLifetime.
The final cases overlap earlier probes, not additive recovery counts. This is the
review gate for a reusable durable fixture, not28 original-failure closure, durable
feedback service/HTTP regression or full product acceptance. Next stage: after
review, default-collected service and ordinary-login HTTP feedback regression, then
reviewed28 consumer adaptation. Original dated evidence remains unchanged.
