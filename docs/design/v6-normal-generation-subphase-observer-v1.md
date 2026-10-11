# One normal V6 PostgreSQL generation subphase measurement

Status: source-only proposal on preserved9fd75ab. No plugin implementation,
collection or execution yet. Separate root/reviewer authorization is required.
Diagnostics01 classified one new generate/pre_cas/fact_age_outside_window refusal;
it did not localize cost. The ten-call source census is static, not timing evidence.

## Case and original behavior

Select the existing positive owner variant of
`tests/test_owner_review_runtime_api.py::test_actual_owner_review_generation_history_export_replay`
on PostgreSQL, expected collected suffix `[postgres-owner]` (verify exact node by
later authorized collection). This is normal owner generation, not either failed
or passing deliberate six-second-delay test. No sleeps, clocks, fact refreshes,
guards, callback results, graph data or deadlines change. Its existing later
history/export/manual-decision/replay assertions remain. A first failure stops;
no second measurement, retry, truncated success claim or acceptance substitution.

The external pytest plugin lives in a unique evidence directory outside source.
Bind actual application HEAD/all relevant source hashes, plugin hash, exact node,
environment, original collection and fresh outputs in the run manifest. Single
pytest/heavy slot, existing resource floors, local MockHTTP only. Preserve normal
fixed diagnostic logger output as evidence, without attaching a handler that
collects arbitrary logs. No general tracing, stack capture or Pydantic descriptor
wrapping. Existing base observer/census techniques inform implementation, but a
new exact source review must verify this narrower fixed list on the chosen HEAD.

## Nonoverlapping accounting first

Use one ContextVar operation state per original PlanningDocumentService.generate
invocation. Patch that class method with an ordinary function wrapper preserving
its descriptor, signature metadata and original-once behavior. At most four such
operations (first generation and saved request replay can both occur); each report
has a local bounded ordinal and separate outcome, never identifiers/request keys.

Wrap repository.save_generation once. It starts an explicit save root frame and
wraps ONLY its received `recheck` keyword callable in a per-invocation original-once
`final_sources` timing wrapper. The closure itself is local/unpatchable by module
name; don't substitute its implementation or search closures. Preserve all original
other arguments and the callback's exact arguments/result/exception. Fail setup
on signature/binding drift BEFORE the customer operation, not midway through it.
Do not retain callback/argument references after the call completes.

Immediate save children have these fixed labels:

- generation_entry: repository._generation_entry
- actual_bindings: repository._generation_actual_bindings
- owner_bindings: repository._generation_owner_binding
- final_sources: the exact recheck callable described above
- retained_capture: repository.capture_retained_sources (verify identity with
  retained_sources.capture_retained_sources, patch both aliases once)
- storage_pair: repository.plan_version_storage_pair and storage.plan_version_storage_pair (verify identical alias)
- flush: Session.flush only while a save root is active; original descriptor and
  no return/exception changes. Nested flush attribution remains in its actual parent.

Every frame records inclusive wall duration and accumulated DIRECT-child wall
union; exclusive=inclusive−sum(direct children), not sum of all descendants.
The save report's top-level partition is the exclusive root residual plus its
immediate child inclusive intervals. If another wrapper lies below an immediate
child, it must NOT also enter that top-level sum. Report both tree parent ordinal
and aggregated labels. Replay is separate and may omit most labels legitimately.
Retained capture may fail; close frames in finally and preserve original exception.

Save residual explicitly includes unwrapped ownership/receipt/head/parent SQL,
paid/goal/account/privacy work, CAS, dependency/receipt construction, unwrapped
serialization and observer overhead. Never call residual pure validation or lock
wait. Before/after save portions remain generation residual, not attributed to save.

## Fixed nested decomposition where needed

To make a large final_sources or retained_capture interval actionable, additionally
wrap these ordinary functions with exact alias identity checks during setup:

- service.recheck_selected_paired_sources plus selected_paired_local alias: label
  selected_current, bounded call ordinals distinguish the two fresh selected passes.
- creative_finalization.recheck_collected_creative plus service alias: image_current.
- owner_review_generation.recheck_owner_review_input_receipts plus service alias:
  original_receipt_current (includes SQL and local strict binding).
- google_budget_owner_retained.capture_owner_review_retained_sources: owner_retained.
- google_budget_owner_retained._owner_evidence: owner_original_evidence; preserve
  the two separated original-receipt loads, never cache their outputs.
- creative_retained_sources._Context.__init__: retained_context; preserve the
  original ordinary method descriptor and return None. This bounds mandatory
  document validation plus transaction checks without wrapping Pydantic descriptors.
- creative_retained_sources._capture_creative_retained_sources: creative_retained.
- selected_plan_witnesses.capture_selected_reporting_sources plus imported alias
  in creative_retained_sources: selected_retained.
- creative_currentness._capture_creative_retained_source: image_retained.
- creative_history._creative_local_witness plus the imported alias in
  creative_retained_sources: creative_witness; dynamic import in currentness sees
  the same wrapped defining function. No validation is removed.

All remain nested children, not additive top-level cost. No model_validate, serializer,
per-row generic ORM method or provider callback instrumentation. This deliberately
leaves intrinsic model cost within its named ordinary-function envelope; a large
owner_bindings result would justify later source-specific investigation, not an
assumption all of its duration is owner model CPU. Any uncertain alias is resolved
read-only before plugin freeze; missing or changed identity blocks execution.

## Counters, authority brackets and limits

Use real perf_counter for elapsed and process_time for optional CPU. Process CPU
is process-wide, not thread-exclusive; label it accordingly. Observer clocks never
replace authority.time, service clock or database time. Optional SQLAlchemy engine
before/after/error listeners retain only integer count and monotonic duration in
active frames; discard statements, parameters, connections and contexts immediately.
Attribute each SQL count/duration to the deepest active span exactly once, or
explicit unassigned save residual if no child is active. Parent inclusive values
aggregate descendant counters; do not sum parent+child in the top-level report.
Include completed and failed SQL counts separately. SQL duration is inclusive
execution/listener time, not lock-time attribution. No SQL text/hash/shape logging.

At save entry record real monotonic−the resident fact.completed_monotonic as a
sampled fact-age bracket (numeric only), and at save exit similarly. Wrap original
authority.final only during active generation to record fixed diagnostic_phase,
returned/raised outcome and before/after sampled age brackets. Read only the known
resident dataclass scalar, never principal/session ORM fields. No extra session
expiry read or wall-clock sample. The original final samples its own clock and
predicate; observer samples are brackets, NOT exact predicate values. Use no fact
object map or identity, no user/session/account/plan IDs. Nonfinite/invalid sampled
values become fixed unavailable, not arbitrary repr/error. Do not change the fact.

Bound report to four generation operations,32save roots,total512 frames and128final
calls per operation, maximum256KiB canonical output. If any cap is reached, set
truncated=true, stop adding records and continue original application behavior.
A truncated report cannot support complete coverage or exclusive partition claims.
No per-row call explosion. Metric recording failures must be caught in observer
code only; original function/exception must still return/rethrow unchanged. Do not
wrap original execution in a broad suppression block. Parent/stack cleanup is in
finally; restoration removes every listener and restores exact original functions,
even if setup partially fails or output persistence fails. Do not remove another
plugin's replacement; detect mismatch as fixed incomplete/restoration status.

pytest_sessionfinish writes the bounded report to an exclusive fresh file. Catch
persistence/serialization failures, emit only a fixed safe stderr message, preserve
original pytest exit status, and always restore instrumentation. Test runner writes
original exit before parsing XML/report. Report/application/manifest hashes and
all outcomes, including failure and unrun assertions, stay durable. No credentials,
args, exception text, request/response data, SQL or raw logger capture in report.

## Interpretation and next decision

A usable report provides a disjoint save partition plus nested breakdown, original
fixed expiry phase/cause if refusal occurs, sampled final-fact envelope and explicit
unattributed/observer limits. A pass does not disprove the earlier failure; a failure
does not automatically identify a root cause from the largest inclusive subtree.
Only a reproducible source mechanism consistent with measured dominance can justify
a bounded repair. No optimization or follow-up execution is automatically authorized.
The resulting repair must retain all current SQL/fresh proof passes, strict public
copied validation, original five-second authority, privacy and atomic rollback.
