# B17 Operational Reported Feedback: Proposed Implementation Contract

Proposal against `31a412d`; migration reservation `0077` down `0076`. No code or
production policy is installed by this proposal. Read the complete
[basis](b17-operational-feedback-next-package.md). Strict v3/directional schemas,
qualification, execution and financial gates remain unchanged.

## Bounded Product Slice

Meta campaign-level existing budget action only: manual Sales/Auction, exact current
campaign budget owner/cohort, no ad-set extrapolation, unknown receipt, paused
creation, status action or new campaign. An original action request selects a
server-defined equal-length pair of closed local-date windows: before ends no later
than dispatch; after starts no earlier than the latest successful configuration
observation. Exclude the entire observation bracket. Require equal weekday composition
(initially whole-week lengths required by explicit server policy), exact selected
purchase event/query/currency/timezone and native/source generation. State explicitly
that unseen external edits and delivery onset remain unknown.

## Frozen Names And Service Ports To Implement After Approval

New package `app/reported_feedback`, distinct from `outcome_feedback`:

- `ConfigurationObservationAnchorV1`: workspace/account/integration/generation,
  campaign ID and external ID, immutable original attempt/request/plan digests,
  current reservation/ledger, latest receipt ID/sequence/digest, actual dispatch and
  configuration-observed timestamps, exact before/after configuration digests,
  current goal/revision/digest and privacy revision. Fixed interpretation
  `configuration_observed_not_delivery_effective`; delivery time/causal lift unavailable.
  Resolver follows unique current held owner lineage; a newer unresolved attempt
  blocks rather than selecting an old successful receipt. No protection tables mutate.
- `ReportedWindowPolicyV1`: required server ID/family/revision/environment; selected
  purchase event/query version, window days, close age, distinct completion count,
  minimum repeat spacing, maximum acquisition/source age, per-day absolute/relative
  revision tolerance, minimum conversions/spend, retention/row/request limits and
  decision lifetime. All numeric parameters required, bounded structurally, with no
  default or production registry entry. Policy family stable across recalibration.
- `ReportedWindowCapsuleV1`: source/anchor cohort, exact inclusive date window,
  native completion ID/manifest digest, actual acquisition start/completion time,
  capture time, expiry; ordered daily tuples (date, spend micros, selected conversions,
  selected conversion-value availability). Explicit expected/reported/missing dates
  and daily-data digest. Never infer a missing day as zero or use aggregate count as
  exact coverage. Actual zero rows are retained as zero. Separate schema from0075.
- `OperationalReportedComparisonV1`: anchor and all before/after capsule commitments,
  policy commitment, window coverage, latest values/CPA, repeated as-of acquisition
  chronology and tolerance result. `operational_reported_as_of` or `insufficient`;
  insufficient has fixed reasons and no recommendation delta. Stability is observed
  report agreement, not independent reconciliation, settled correction or causal lift.
- `ReportedFeedbackPolicyV1`: required mapping by original increase/decrease cohort,
  minimum usable comparisons, weight, neutral band, per-contribution and aggregate
  clamps, preview delta cap and lifetime. Family/revision explicit; no5/10/20 reuse.
- `ReportedFeedbackPreviewV1`: comparison and active-set digests, original baseline
  preview commitment, before/after CPA, policy/explanation, bounded recomputed delta,
  resulting preview and expiry. `spending_authority=none`; review handoff unavailable.

Service entrypoints (caller IDs/intent only):
`request_comparison(db, principal, identity, attempt_id, objective_id, runtime)`;
`advance_fixed_window(engine, runtime, now)`;
`read_comparison(db, principal, identity, request_id, runtime)`;
`apply_feedback_preview(db, principal, identity, comparison_id, baseline_preview_id,
runtime)`. Reads/application check the original session, goal, source, latest receipt,
policy and every dependency with effective application/database clocks. No request
accepts policy parameters, timing proof, metrics, cohort or desired direction.

## Acquisition: Reuse Actual Meta Staging, Not Rolling Re-import Labels

Introduce one durable fixed-window acquisition request linked to the exact original
session/anchor and policy. A request owns a bounded sequential list of before/after
re-observation windows and due times; repeats are scheduled only after explicit
spacing, never fabricated by recapturing one completion.

At the *existing new-run boundary* in `MetaSyncService.page`, after workspace/native
locks and before choosing the default56-day range, a server scheduler hook may claim
one due owned fixed-window request. A running rolling/detail import is never
interrupted or its checkpoint rewritten. The claim stores selected window, native
source generation and an explicit new run commitment. Existing inventory, campaign
insights, pagination, credential, backoff and terminal-publication paths execute the
real request. Keep per-tick page/request bounds; queue capacity/expiry are explicit.
Regular rolling work must not starve behind the bounded request queue.

The terminal transaction creates the native performance completion and captures the
requested campaign's actual daily rows before the next publication can overwrite
them; advances the acquisition request only for its exact run/generation/window.
No customer identity callback/network call runs while publication locks are held;
local current session/membership checks fence the publication, with external identity
revocation verification at customer admission/read. Revoke/reconnect/privacy retires
requests and clears existing staging through the same lifecycle path. An interrupted
unpublished page cannot become a complete capsule. Native API IO remains the existing
bounded client path; new customer HTTP requests enqueue rather than block on scans.

Important integration detail: fixed-window acquisitions must not imply that the
normal rolling56-day coverage just advanced. Track their completion separately from
rolling cadence/coverage; preserve ordinary import scheduling and older daily values
outside the exact imported interval. Child-detail behavior remains existing; if it
makes this slice needlessly broad, a separately typed campaign-only phase must be
approved before implementation, never a silent detail override.

## Proposed0077 Schema

Five minimal table families, each scalar scope bound with compound foreign keys:

1. `reported_feedback_jobs`: owned account/campaign/source generation, original
   attempt and original actor/session, policy/anchor JSON+digests, pair/round/phase,
   due/expiry, native run commitment, fixed state and sanitized error. One active job
   per original-attempt/family/cohort; capacity bounded. Classified erasable derived
   read queue in lifecycle worker registry, never finance/retry authority.
2. `reported_window_capsules`: owned immutable daily document/digest, native completion
   FK, job/run/window/repeat identity, acquisition/capture/expiry. Unique terminal
   completion+campaign+environment. Raw report identity already scoped by importer.
3. `reported_action_comparisons`: owned anchor/comparison document+digest, original
   attempt/latest receipt commitment, policy/family/cohort, expiry. Numeric derived data.
4. `reported_comparison_dependencies`: compound owned comparison→capsule FKs; deletion
   or correction of *any* dependency erases the entire comparison, not just its edge.
5. `reported_feedback_slots`: one current contribution/preview document per original
   attempt+family+cohort; FK to comparison and exact owned initial baseline preview.
   Required revision/digest and expiry; policy revision/correction do not create a
   second active slot. Recompute from bounded active slots, never compound a prior
   feedback-adjusted preview. If baseline preview is retracted, dependent slot vanishes.

Corrections discovered by same-window acquisition compare exact retained day values,
retract all dependent numeric comparisons/slots and restart stability qualification
from the changed report. Conservative workspace-derived invalidation is acceptable
for source/privacy/receipt change; it must leave protected attempts/holds/receipts
untouched. Existing0075 invalidation/export revision functions gain narrow additive
hooks. DB cascade/trigger guards preserve erasure under direct dependency deletion;
read-time expiry is mandatory even before cleanup. App/DB clocks enforce retention.

Lifecycle/export: all five are customer-owned erasable derived records; no credentials
or session digest exported. Typed serializers verify document/scalar ownership and
expiry; capture+stream privacy revisions invalidate stale archives. Privacy/reconnect,
new receipt, policy change or session end cannot leave a usable old numeric preview.
Like0075, a capsule's captured global export counter is audit-only: ordinary
calibration invalidation may increment it without erasing history. Semantic privacy
hooks physically delete capsules; compare source generation, all retained dependency
commitments and current request/session authority instead of requiring every older
repeat capsule to equal today's export counter. Export streaming still checks its
captured global revision. Create/select the baseline preview after acquisitions;
a later normal import may invalidate that preview and therefore the feedback slot.

Financial amounts inside protected provider records are not reclassified as these
new report-derived values.

## Customer Consumer And Acceptance

Add an owned History/Initial Planning comparison request/status/detail surface and
"Update Preview From This Comparison" action. Show both windows/CPAs, observation
bracket, missing dates/revision changes, repeated observations, explicit policy and
noncausal explanation. Returning an assessment alone is not completion. No dependent
0076 review handoff is required: new preview remains non-authorizing and review unavailable.

Acceptance must trace actual injected Meta HTTP pages through terminal publication,
repeat same-window capsules, actual owned optimization receipt, comparison, active
slot and changed customer-visible preview. Include both DBs, bounded browser/API path,
unknown later receipt/no older fallback, correction during acquisition/final read,
delayed capture, missing days, zero conversions, duplicate request/idempotent slot,
retraction/reapplication stable original opportunity, logout/reconnect/privacy/expiry,
foreign scope and protected-finance survival. No Full/live calls for this package.

## Approval/Frozen-Port Checkpoint

Parent approved the five-table layout and new-run/terminal hooks before implementation.
The frozen ports live in `app/reported_feedback/{contracts,models,runtime,ports}.py`.
Concrete consumer functions will live in `app/reported_feedback/service.py` with the
protocol signatures: `request_comparison`, `read_comparison_progress`, `read_comparison`,
`apply_feedback_preview`, `read_feedback_preview`. Acquisition hooks will live in
`app/reported_feedback/acquisition.py`: `claim_fixed_window` and `capture_terminal_window`.
The caller owns service transactions; jobs own bounded native phases. No production
parameter values or native qualification are selected.

Parent refinements are mandatory: consider due fixed work before the rolling
up-to-date shortcut, but rolling-due work wins to prevent starvation. Preserve rolling
covered dates/last_sync/cadence and existing detail-enabled behavior. Save actual
acquisition start once (never use mutable last_attempt_at). Background publication
requires a still-valid local original session/member/source; final customer delivery
also checks current external identity. Capsule/global privacy counters are audit-only,
with semantic erasure hooks; distinct original attempts, not recreated jobs or receipt
revisions, count toward active feedback. Baseline preview is created after acquisition
and may legitimately disappear at the next import.

Freeze validation: four focused contract regressions; whole-tree Ruff/mypy and diff
checks. These verify contracts, not operational integration. Model registry, migration,
triggers, acquisition/service and customer consumer remain implementation work.
