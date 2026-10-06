# B19 Runtime Observation Proposal

Design only, inspected root `a1a91e7`. No shared code/schema edits, migration
reservation, runtime enablement or live requests. The existing operator attention
endpoint remains observational; timestamps never authorize retry or termination.

## Concrete Current Paths

- `app/operations/attention.py` samples JobRun and source/coordinator states, but
  explicitly lists storage, heartbeat, never-started work and AnalysisRun gaps.
- `JobRun` requires workspace and advertising platform. It models admitted jobs,
  including a start time; manufacturing a Google/platform/workspace row for a
  global scheduler or storage failure would misstate ownership and job semantics.
- `AnalysisRun` already records exact workspace/run_key, cadence, source job,
  scheduled/start/finish times and strict running/succeeded/failed states. Reuse it
  for analysis observations; no new analysis history table.
- `GoogleImportCompletion` is the durable post-import analysis obligation used by
  customer Google/TikTok dispatch. It has pending/delivered state and next-attempt
  time, joined to an owned JobRun. The source job's finish time anchors first due
  time; it does not prove an analysis process was ever started.
- `google_ads_scheduler.main` invokes legacy sync and `_run_analysis_tick`; the
  latter invokes independent source/privacy/customer stages then local analysis.
  Some exceptions become fixed log messages only. It does not persist a loop
  checkpoint. `run_customer_tick` returns fixed completed/failed stage outcomes,
  but a completed call can legitimately have no eligible work.
- LocalMediaStore performs owned local read/write; GCSMediaStore sanitizes remote
  errors to OSError. `get_media_store` initialization produces sanitized503 on
  failure. These are the actual private-media storage paths; export delivery and
  future storage backends must not be silently included in their coverage claim.

## Package A — Existing Durable Evidence, No Migration

Recommend implementing this first, exclusively in operations attention/tests/docs:

1. Add `analysis_failed` and `analysis_running_overdue`. Sample up to501 scalar
   AnalysisRun rows joined to active workspaces, inspect500, preserve lower-bound
   truncation. The identity is workspace/cadence/account/source-job/run_key; newer
   state of the exact run dominates, not an unrelated successful analysis. Do not
   parse decision briefs, error strings, customer content or retry history.
2. Add `analysis_obligation_unstarted_overdue`: pending GoogleImportCompletion
   joined through exact source JobRun/workspace, with no AnalysisRun for that exact
   workspace/source_job_id. Use next_attempt_at when present, else source job
   finished_at, and the existing900-second engineering observation threshold.
   Missing source finish time stays unknown, never invented. Scope is post-import
   analysis only, not every possible scheduled job.
3. If a pending obligation has a recorded analysis run, do not label it unstarted;
   existing running/failed observations explain it. Future backoff suppresses the
   overdue signal. Closed workspaces are excluded as with current job attention.
4. These are inspection signals, not a finding that work must legally run now:
   entitlement/automation/source changes may intentionally prevent delivery. Do
   not duplicate or override their admission policies. Explain that queued work
   may be paused/blocked, and route operators to existing scoped tools.
5. Replace the broad local-analysis gap with narrower explicit coverage gaps:
   unscheduled/no-obligation nightly/weekly work is not observed; a scheduler that
   never records a checkpoint is still unobserved; storage remains unobserved.
   There is no claim of general “never-started work detected.”

Shared response contract additions are fixed literal codes/action `inspect_local_job`
plus a slightly larger bounded signals list. Preserve existing operator authorization,
no-store response, scalar-only sampling, two-second PostgreSQL statement timeout,
truncation flags and sanitized503. No new customer routes, scheduler policy, source,
exposure, billing, media model or candidate changes.

Acceptance: SQLite/PostgreSQL analysis failure/running boundary, newer same-run
recovery, pending obligation without a run, same job ID/cross-workspace denial,
future retry, observed run suppressing unstarted, closed workspace, null due time,
truncation, fixed-code sanitization and operator-only route matrix.

## Package B — Genuine Scheduler/Storage Instrumentation Requires A New Contract

Do not overload JobRun or AnalysisRun. Propose one bounded operational-observation
table, only after root approves a migration reservation and lifecycle inventory:

`OperationalObservation` key `(component, slot)` using fixed allowlisted enums.
Initial components: scheduler_loop, private_media_local, private_media_gcs.
Slots: latest_start, latest_completion, latest_failure. At most9 rows; no arbitrary
labels, workspace/account IDs, bucket/object/path names, host/PID/IP identifiers,
exceptions, messages, JSON, credentials or customer payloads. Columns: observed_at,
optional expected_next_at (scheduler only), fixed outcome code, optional random
process_epoch for scheduler observations, and bounded/saturating occurrence counter.
Counters count observed operations, not unique incidents or confirmed losses.

Use a strict `ObservationSink.record(Observation)` protocol with an explicitly
injected DB implementation owning a short, independent transaction. Upsert one
allowlisted row; keep only the newest timestamp and increment bounded counts under
concurrency. Failed telemetry writes emit one fixed fallback log code and cannot
mask or change the original storage/worker result. No telemetry retries, recursion,
provider calls or storage probes. DB unavailability remains an explicit observation
gap; it cannot be reported as healthy. The independent transaction must not acquire
workspace/source locks held by the failed operation.

Instrument actual scheduler loop boundaries after runtime initialization and after
all attempted stages. Store cycle start/checkpoint and completion separately;
propagate fixed stage-failure classification so “loop completed” does not assert
all components succeeded. Explicit skipped/disabled outcomes stay distinct. Record
expected next wake at the actual calculated interval boundary. A late checkpoint
means “scheduler observation overdue,” never worker dead/terminated or safe to retry.
No background heartbeat thread that could report a healthy loop while useful work
is stalled. No lease replacement or cancellation based on heartbeat age.

Instrument private-media initialization/read/write through a thin MediaStore
wrapper, preserving the existing owned scopes, byte checks and exact exceptions.
Record fixed operation/read_failed/write_failed/init_failed classifications only;
never pass exception text or media scope into the sink. Do not change retries,
storage policies, privacy deletion or export source ownership. Mock GCS/local faults
must call the sink without changing provider/network behavior. Scope the coverage
name to private-media operations; uninstrumented storage remains an explicit gap.

A durable checkpoint cannot prove a scheduler never ran before instrumentation.
An empty observation table means “no scheduler observation,” not global failure.
Distinguishing “expected but never observed” requires an explicit deployment-owned
expectation and its activation time. There is no such durable expectation today.
Recommend keeping that separate rather than adding fake start rows or inferring an
SLO from process elapsed time. Root can approve an exact expectation contract later.

Additional acceptance: bounded upsert concurrency and failure isolation on both DBs;
actual scheduler main invocation with injected operations, including disabled,
exception, interrupted and delayed cycles; no cross-epoch overwrite of newer
observations; slow/stuck cycle yields overdue observation without process-state or
retry claims; local/GCS injected faults emit fixed codes and never identifiers;
rollback of failed customer work cannot erase an already-recorded operational
failure; telemetry DB failure preserves original operation exception. Migration
roundtrip and lifecycle/export classification required before integration.

## Boundaries And Recommendation

Approve Package A now to close existing analysis and a narrowly provable unstarted
obligation gap without a schema. Review Package B's shared observation port/table
and ownership before code. External alert destination, escalation policy, deployed
runtime evidence and live delivery remain separate release gates. Neither package
qualifies storage availability, advertising spend, provider outcomes or recovery.
