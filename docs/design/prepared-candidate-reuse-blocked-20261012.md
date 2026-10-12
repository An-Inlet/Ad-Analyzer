# Prepared Candidate Reuse: Implemented, Qualification Blocked

Local branch: `codex/inlet-w1-followup`. Base and current committed head:
`f8107a9c5f60accb5e73e6d9fa82a5b4e33021dd`. This package is uncommitted;
no push, PR, hosted CI, merge, deployment, provider call, credential operation,
customer advertising change or spend occurred. V3 remains the default. V6/V7
selectors are technically available and release-unqualified, not technically disabled.

## Implementation And Boundaries

`prepared_candidate.py` reuses the candidate already validated during generation
preparation. It admits exact bounded schema/scalar snapshots including nested field
sets, takes a detached private copy, and checks fresh equality before each retained
validation replay. Changed model validators, serializers, application helper bindings,
methods, storage descriptors or constructors fall back to ordinary validation.
Ordinary validation may itself call the changed constructor; its result or refusal
is preserved. Before preparation, a changed constructor disables copying entirely.
The constructor guard explicitly includes inherited `__new__`, which Pydantic's
`__deepcopy__` invokes. This is a bounded application contract, not protection against
arbitrary in-process mutation of Python/Pydantic globals or copy registries.

The replay scope is bound to the existing preparation, exact Session/root/connection,
thread and async task. It has no cross-request reuse and caches no authorization or
SQL result. All existing reads and dynamic boundaries remain. Seven retained
validation calls can reuse detached copies. At most 16 issued graphs are tracked;
each is sealed against the prepared snapshot before retained witnesses escape.
Mutation of an issued graph conservatively refuses acceptance through the existing
409 path. This tightening is not claimed to restore every former aliasing behavior.
Normal Pydantic validation creates a new PlanVersion root but can share field-set
metadata; private deepcopy prevents that alias. Exceptions retain their original
identity, cleanup clears private state, and unsupported cases use ordinary validation.
Snapshot limits are 100,000 nodes, depth 128 and 8 MiB accounting units per root,
not a bound on total process heap.

## Qualification Evidence

Evidence roots below are under `/workspace/inlet-evidence/20261012`.
Every attempt has frozen sources, exact commands, original exits and logs/XML;
failures were preserved rather than retried unchanged for acceptance.

| Attempt | Result And Disposition |
| --- | --- |
| prepared-candidate01 | Ruff passed; mypy failed on two test annotations; later checks unrun. |
| prepared-candidate02 | Four statics passed; one component passed, then incorrect nested-mutation oracle failed. |
| prepared-candidate03 | Four statics and 12 components passed; shared field-set fixture alias failed. Fixed fixture isolation; removed an impossible read-only `__dict__` replacement variant before execution. |
| prepared-candidate04 | Four statics and 58 tests passed; superseded by the issued-graph sealing correction. No acceptance credit for later source. |
| prepared-candidate05 | Ruff passed; mypy failed on a new runtime-test annotation; later checks unrun. |
| prepared-candidate06 | Four statics and 18 components passed; incorrect fallback identity oracle failed. Replaced with value and original-validation-call assertions. |
| prepared-candidate07 | Four statics, 43 components, 10 SQLite and eight PostgreSQL tests passed. PostgreSQL post-flush expiry case failed before its deliberate delay. One remaining PostgreSQL v5 case unrun. Overall 61 passed / one failed / one unrun. Package remains failed/incomplete. |
| expiry-recorder01 | Ruff passed; mypy failed on two recorder annotations; later checks unrun. |
| expiry-recorder02 | Four statics and four recorder microtests passed; 1,923 source hashes verified. |
| candidate-constructor01 | Four statics and 20 components passed; the next fixture errored after constructor mutation affected a CPython slot. No product change; isolate the actual constructor mutations in bounded child processes. Four recorder cases unrun. |
| candidate-constructor02 | Four statics and 20 components passed; warmed-child oracle incorrectly expected ordinary validation not to call the changed constructor. A bounded child diagnostic confirmed fallback was correct. Four recorder cases unrun. |
| candidate-constructor03 | Ruff passed; mypy rejected test introspection through `__func__`. Used the bound method's directly available `__code__`; no behavior change. Later checks unrun. |
| candidate-constructor04 | Four statics and 20 components passed; test counter included other calls sharing BaseModel's validation code. Diagnostic counted three shared-code calls, one constructor and zero copies. Restrict counter to PlanVersion validation directly from the replay helper. Four recorder cases unrun. |
| candidate-constructor05 | Four statics (Ruff, mypy over 1,605 files, exact collection and diff check) and 25 focused tests passed; 1,923 source hashes verified. Manifest `477a670eb97fcb6e8d10d15d1127d0088abcec95b32c538990036302c8b9dd74`. This qualifies the focused guard/recorder checks only, not the failed package. |

The failed attempt07 node is
`tests/test_prepared_generation_runtime.py::test_configured_real_expiry_preserves_complete_rollback[postgres-post_flush]`.
Its `delayed == [True]` assertion observed `[]`; response/caplog were not retained.
The cause is unknown. Earlier authority expiry is a hypothesis, not an established
cause. The remaining unrun node is
`tests/test_creative_retained_dispatch.py::test_actual_generic_v5_viewer_unpaid_complete_witnesses[postgres-1]`.
Do not convert the original failure to a pass based on later diagnostics.

The failure-safe expiry recorder now retains status, an allowlisted response category,
delay state and validated fixed authority fields in `finally`, including malformed
JSON and failing-output cases. It retains no raw response body. Recorder failures
cannot replace an active request/assertion exception. Original delay, deadline,
rollback and refusal assertions are unchanged.

## Single Diagnostic: No Qualification Credit

`prepared-candidate-postflush-diagnostic01` ran the exact failed node once with
unchanged production source from attempt07 and the new recorder. Manifest:
`0665d8c6853134b2164b3a65537072562bd11050bb83f1f753f5f89bfca18337`.
The initial launch guard refused insufficient memory before starting a test. Releasing
clean task-owned cache pages restored headroom; no files were deleted or modified.
The actual diagnostic invocation exited 0 in 27.185 seconds, with clean process and
observer cleanup and all 1,923 source hashes verified. It reached the six-second delay,
returned 409 `planning_authority_expired` at post_flush, and passed complete rollback
assertions. This neither reproduced nor explained attempt07's early exit.

Observed candidate preparation/copy cost before final refresh: 0.023705 seconds.
Seven candidate helper calls took 0.071793 inclusive seconds; 14 fresh snapshots
(including scope-exit seals) took 0.076468 inclusive seconds. Nested measurements
must not be added. The monitored final phase took 8.488948 seconds including the
six-second negative-control delay, with 2.162869 thread CPU seconds and 2,387 SQL
executions. Three ordinary PlanVersion validations remained outside candidate replay.
These are observer-instrumented negative-control observations, not a successful normal
workflow benchmark, paired speedup, latency target, capacity or release qualification.
The normal configured HTTP/browser workflow was not run for this package.

## Preservation And Next Package

All 21 pre-existing pending HTTP files were preserved: 18 source files compared with
`generation-worker-sampling01` hashes (removing only the two committed f810 service
additions for comparison), and three documents compared byte-for-byte with their
`selected-reconstruction01` frozen copies. Evidence:
`prepared-candidate-pending-preservation.json`. Migration 0094 and prior safeguards
remain unchanged. Original incident `INLET-REL-20261012-01` remains open; no causal
identity is claimed. HTTP inventory remains 57 passing / one unresolved, and the
reconnect-retention owner decision is still pending.

Independent source review closed the recorder, constructor guard and diagnostic
disposition. Commit, normal workflow and release-matrix execution remain held because
the package qualification failed. There is no justified causal production repair for
attempt07 yet. Preserve this evidence gap rather than run unchanged until green.

The next finite release package should prepare the previously proposed 18-scenario
matrix (two fixture sizes, three request patterns, three arrival offsets), not continue
speculative microoptimizations. Before execution, declare valid combined fixture
counts and document bytes; parameterize small/large owners; preopen asynchronous
lock observers; remove winner-held waits; enforce real 0/50/250 ms client arrivals
before authentication; and route distinct workspaces without changing global app
fixtures during requests. Add harness checks for both outcomes, cleanup, exact
same-key replay, expected different-key conflict and workspace isolation. Pin PostgreSQL,
pool and timeout settings, SQLite parity/negative-control nodes, complete-to-partial
placement, designated actual-overlap requirements, 900-second case and 60-minute
package limits. Missing overlap is a coverage gap without retry. Retain all existing
resource floors and the 1,536 MiB diagnostic/browser launch reserve. The harness is
not ready for execution as-is; qualification failure remains a separate blocker.
