# Owned Current Goal Sales Progress

Design-only proposal at fa6a834. No new persistence, retention, numeric policy,
provider call, model interpretation, advertising authority or causal attribution.

## Existing Components And Actual Gap

- `app/portal/static/portal.mjs:editGoal` currently prints that sales progress is
  unavailable. `GoalDefinition` already binds immutable revision, target amount,
  exact target/baseline local windows, store, currency and named time zone.
- `app/commerce/reporting.py:measurement(...,snapshot=False)` reads the current
  merchandise ledger. It preserves `shopify_merchandise_net_sales_v1`, verifies
  owned active store/integration, basis, history/retention, completed import,
  freshness, reconciliation and privacy suppression. It uses the existing24-hour
  freshness and existing retention floor; this package does not change either.
- `app/commerce/ledger.py` records refunds at `refund.processedAt`, not original
  purchase time. Entries may be negative. Shipping/tax/excluded lines must not be
  reintroduced by a second progress calculator.
- `CommerceSyncService.page` publishes last_sync_at only after full pagination;
  window_end marks ongoing import. Reconnect clears current coverage. An import
  watermark is not immutable economic finality or independent reconciliation.
- The whole open target window produces incomplete_window today. Reusing its
  observed_net_sales_micros would bypass quality gates. The missing implementation
  is a bounded closed-day prefix projection plus owned API and portal rendering.

## Proposed Minimal Semantics

Read the exact current goal revision, never a customer-supplied measurement window.
Require a recorded confirmation for that revision and a valid definition. Drafts
return unavailable/goal_not_confirmed, with no sales amount. Do not reinterpret
baseline freshness as target progress: a stale historical baseline and a current
confirmed definition are separate facts. This response does not reconfirm the goal.

For an active owned store, compute its local calendar date at fresh DB/application
wall time. Compute the local calendar date of the completed import watermark.
The measured exclusive end is min(target.end, local_today, watermark_local_date).
Thus only fully closed local days covered by a completed import are displayed;
never label the in-progress day as complete. If end<=target.start, return
not_started or unavailable/no_closed_days without a manufactured zero amount.

For a nonempty prefix, call existing measurement with identical start/currency/
timezone and an internal cumulative MeasurementWindow ending at that date. The
original target_window and time_basis in the response stay unchanged: the prefix
is a display interval, not a goal revision or switch to a cumulative objective.
Validate local midnight boundaries using the existing strict roundtrip/fold pattern
from customer_plan_review.exact_period before measurement; reject ambiguous or
nonexistent boundaries. No browser-zone conversion and no 24-hour-day arithmetic.

Only measurement quality=complete admits net_sales_micros. Otherwise the amount is
null and existing reasons are projected through a fixed enum. Never expose its
observed_net_sales_micros fallback. Genuine complete zero is zero; refunds may yield
negative values. No clipping, extrapolation, sales-rate forecast, causal lift,
remaining ad budget or advertising contribution is inferred.

The projection says partial_period if measured end<target.end, otherwise
full_window_as_of. Both are mutable as-of imported sales, not a final goal-achieved
verdict. No goal-achieved flag or celebratory completion state. UI may compare the
signed measured amount with target in money terms but must retain as-of/coverage
wording even when the recorded amount is greater than the target.

## Exact Proposed Shared Response

New `app/goals/progress_contracts.py`, frozen strict models (extra forbidden).
Identifier strings retain existing goal/store local ID constraints.

```python
ProgressReason = Literal[
    "goal_not_confirmed", "goal_definition_unavailable", "source_unavailable",
    "measurement_basis_changed", "ambiguous_local_boundary", "no_closed_days",
    "outside_retention", "missing_history", "incomplete_window", "stale_source",
    "import_in_progress", "source_error", "unreconciled_source",
    "privacy_suppressed_source",
]

class ClosedDayCoverageV1(Frozen):
    starts_on: date
    ends_on_exclusive: date
    starts_at: AwareDatetime
    ends_at_exclusive: AwareDatetime
    closed_day_count: int  # positive; local dates, not elapsed UTC hours
    extent: Literal["partial_period", "full_window_as_of"]

class GoalSalesProgressV1(Frozen):
    schema_version: Literal["inlet.goal-sales-progress.v1"]
    workspace_id: int
    goal_id: str
    revision: int
    definition_digest: str | None
    metric: Literal["shopify_merchandise_net_sales_v1"]
    status: Literal["available_as_of", "not_started", "unavailable"]
    target_window: MeasurementWindow | None
    target_micros: int | None
    store_id: str | None
    currency: str | None
    time_zone: str | None
    coverage: ClosedDayCoverageV1 | None
    net_sales_micros: int | None  # signed, no artificial positive-only restriction
    source_watermark: AwareDatetime | None
    source_revision: int | None
    import_in_progress: bool | None
    as_of: AwareDatetime
    reasons: tuple[ProgressReason, ...]  # bounded unique enum, not provider text
    goal_achievement: Literal["not_assessed"] = "not_assessed"
    attribution: Literal["unavailable"] = "unavailable"
    spending_authorized: Literal[False] = False
```

Validators require full definition/basis and positive nonempty coverage for
available_as_of; only that status carries a signed amount and has no blocking
reasons. Unavailable/not_started always amount=null. Known definition metadata may
remain visible for an unavailable source; source-derived metadata stays null when
ownership/current source cannot be verified. Endpoints never return customer/order
identities, raw records, snapshots or native resource IDs. Definition digest uses a
new explicit progress-definition namespace over unchanged GoalDefinition JSON; it
is a UI response binding, not a new goal hash/authority protocol.

## Owned Service And Route

```python
read_goal_progress(
    db: Session, principal: CustomerPrincipal, provider: IdentityProvider,
    workspace_id: int, goal_id: str, expected_revision: int,
    *, clock: Callable[[], datetime],
) -> GoalSalesProgressV1
```

GET `/api/customer/v1/workspaces/{wid}/goals/{goal_id}/progress?expected_revision=N`.
Original session, current workspace membership, no-store; GET changes nothing and
needs no CSRF body. Exact expected revision mismatch409; foreign goal404; revoked
session/membership401/403/404. Source-quality failures are typed200 unavailable,
not an unauthorized source dump. Use Principal+Provider and canonical workspace →
user → original session → membership locks via the existing guard with explicitly
allowed existing read roles (owner/admin/analyst/viewer). Then owned goal/current
revision and existing store lock. No network except existing identity verification.
Do not commit or write CommerceSnapshot/history as a side effect.

Sample effective time=max(application UTC, fresh DB wall clock) after blocking
locks/identity checks. Read current source and measurement inside the same workspace
transaction; final original-session/goal/source checks and fresh time before reply.
If freshness/day/retention boundary changes while waiting, recompute against the
fresh time or fail unavailable, never carry entry time through a lock wait. Preserve
existing source/financial lock order and no secret-bearing response fields.

No cache/retained projection means existing commerce erasure/reconnect immediately
removes valid input; no migration/export/retention additions. Browser clears its
progress node on goal/workspace/session/revision change and discards late response
by existing epoch+original-session guards. Selecting a goal triggers this owned GET;
refresh is explicit. A local edit invalidates displayed progress until save/reload.

## Files And Independent Work After Freeze

Backend: new contracts and progress service, additive goal route/tests; reuse existing
measurement unchanged. UI: portal.mjs and minimal progress container in index.html,
no new knobs or milestone interpreter. Shared response freezes before UI work.
No changes to publication, mandates, initial previews, policies or mutable goal data.

Acceptance: both DBs; actual imported order/edit/refund events, refund processed on
later local day; complete zero vs unavailable null vs negative; partial month,
full completed period, future target, no closed days, DST23/25-hour days and rejected
ambiguous midnight; missing history/stale/in-progress/unreconciled/privacy suppressed
source; reconnect/source deletion; goal edit and role/session changes during real
PG lock wait; no snapshot writes; foreign goal/store; actual portal response rendering
and late response invalidation. No full goal-achieved or advertising attribution claim.
