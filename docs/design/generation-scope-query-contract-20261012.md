# Generation Scope Query Attribution And Consolidation Contract

## Decision

Continue from the [critical-path assessment](generation-critical-path-assessment-20261012.md).
The selected historical decoder has no N+1 query: each invocation performs five batched
reads, regardless of its fact loop. The configured final save performs 12 such calls,
60 executions total. Do not add decoder caching or 49 table guards to address its SQL.

Measured amplification is in composed scope/authorization checks. A proposed private
7-to-5 scope-read reuse fast path is **declined before implementation**. Independent
review found its event, ORM refresh, autoflush, overridden-helper and SQLite eligibility
machinery disproportionate to its measured benefit. No authority/transaction cache,
caller-supplied lock token, product change, migration or query removal was implemented.

A replacement query-consolidation implementation must first satisfy the narrow contract
and tests below. This document specifies obligations and blockers; it does not claim a
completed implementation design, query equivalence or a sufficient latency improvement.

## Frozen Evidence And Checks Actually Run

Source branch `codex/inlet-w1-followup`, HEAD
`1881e91a9eb9814a9ad13a82a4589c3d8324227e`.
Evidence: `/workspace/inlet-evidence/20261012/generation-query-diagnostic01`.

- Manifest: `9c4f9d65102b6e7400a016cab020181518a9a2b3f5ff348449749b905cb7e1c2`.
- Observer: `21d8eb3dafd925981d73bfa7c3e10f91df05adcde1a3a57ed85a4b193b00894d`.
- Runner: `2d23d5b38d218e1519b66a73c097f3fe8785777a5daa48f7d49b00dc98cf2c5e`.
- Report: `fdfd04fd6c0090bd97424084759b3bde2539f8d2cceb29b9502add3ef3cf5cf4`.

One exact diagnostic node passed:
`tests/test_google_budget_http_admission.py::test_assembled_http_observation_browser[postgres]`.
Original exit 0; exact passing XML case 55.643 seconds; process 60.306730 seconds.
No interruption, kill escalation or remaining descendants. All 1,915 source hashes,
original Git status and pending HTTP diff verified. No source edits during execution.
Independent preflight and post-run evidence reviews closed. The 903-frame report has
no incomplete frames, observer errors, truncation, incomplete restoration or expiry.

Observer repairs preceded launch and original drafts remain preserved. Cursor timing
starts after query classification. Classification overhead was separately measured at
0.088954 seconds across generation. Bound primitive equality keys remained transient;
the report contains only ordinal identifiers, callsites, counts and durations, with no
SQL text, bound values, value hashes or result rows. Its 51,171-byte binding/statement
payload estimate excludes Python container overhead; independent entry/stack caps and
runtime resource floors remained enforced.

Final save: **2.845934 seconds, 2,385 cursor executions**. Attribution reconciles
2,381 SELECTs plus four non-SELECTs. There were 63 statement shapes and 63 corresponding
binding sets, with no unclassified bindings. Each shape happened to use one binding
set in this fixture. This does not mean its reads saw identical database state.
Callsites retain their enclosing instrumented frame and up to five frozen application
callers, so repetitions across entry/final or media boundaries remain distinguishable.

| Save-scoped helper | Calls | Executions | Inclusive wall seconds | Cursor seconds |
| --- | ---: | ---: | ---: | ---: |
| Historical capture | 12 | 60 | 0.154410 | 0.026800 |
| Selected current scope | 78 | 546 | 0.372047 | 0.158514 |
| Selected aggregate validation | 22 | 704 | 0.504628 | 0.210561 |
| Metric manifest | 48 | 48 | 0.079203 | 0.027111 |
| Selected graph | 12 | 612 | 0.643563 | 0.193696 |
| Selected reporting pin | 4 | 1,156 | 1.240289 | 0.376563 |

These intervals nest and must not be added. Cursor durations exclude fetch,
materialization and most ORM work. Prior diagnostics used different instrumentation
and conditions; differences between runs are not proof of regression or improvement.

The largest exact callsites include privacy revision (165), canonical workspace lock
(144), owned account/integration query (144), each selected workspace/account lock
(102), each of five customer-access reads (98), and fresh database clock (97). Their
repeated binding sets do not authorize removing any observation or expiry check.

## Current Seven-Statement Scope Contract

Each `selected_storage.current_scope` invocation currently supplies these observations,
in order. Keep every invocation: `_aggregate` calls it directly and through entry and
final authorization; other selected reads also call it. No cross-invocation reuse.

| Position | Observation and lock | Required behavior |
| --- | --- | --- |
| 1 | Workspace full ORM row, FOR UPDATE | Workspace exists; acquire this stronger first lock, populate existing state. |
| 2 | Owned AdvertisingAccount full row, FOR UPDATE | Exact account/workspace ownership; missing row raises selected ownership unavailable. |
| 3 | Workspace full row, populate existing | Refresh the resident workspace used by later predicates; preserve required autoflush/refresh behavior. |
| 4 | Workspace full row, NO KEY UPDATE | Shared import validator requires active workspace; preserve import-error translation. |
| 5 | AdvertisingAccount/WorkspaceIntegration inner join plus active Workspace predicate; FOR UPDATE OF account/integration | Exact account/workspace/platform/connection, integration ownership/provider/status, active workspace; refresh resident account/integration. |
| 6 | Platform-native source rows, FOR UPDATE | Exact workspace/account and TikTok provider predicate; cardinality exactly one; preserve source identity/status/error/generation/native/integration checks. |
| 7 | Fresh Workspace export privacy revision | Exact current privacy revision; missing workspace is an error. |

The original Workspace FOR UPDATE is stronger than the later canonical NO KEY UPDATE;
substituting the weaker helper is not equivalent. Existing output is None on success.
Preserve exact account/source scope comparison, current-selection and aggregate checks,
error types/status/details and precedence. Locks remain owned by the caller transaction.

The first consolidation target is workspace observations 3 and 4 within one invocation,
while preserving statements 1, 2, 5, 6 and 7 and all their predicates. Its deterministic
ceiling on this fixture is **156 fewer executions (6.54%)**, not all 546 scope queries.
The two removed callsites contribute roughly **0.04 seconds of cursor time**. There is
no measured optimized end-to-end saving; even removing the entire 0.372047-second scope
cost would not bring this observed save under two seconds.

## Design Constraints And Unresolved Proof

Prefer explicit shared query construction inside a private lexical implementation,
not a reusable authority token or cache. A join must not change missing-account versus
missing/inactive-integration errors, ORM population, cardinality or lock acquisition.
Preserve every external callback and every entry/final database observation boundary.
Do not bypass custom/replaced validation helpers as an incidental optimization.

Open obligations before product changes:

- Identify exactly how observations 3/4 remain satisfied after consolidation, including
  resident ORM refresh and any original autoflush/event behavior.
- Show workspace-first lock ordering for PostgreSQL. A join or CTE alone is not proof of
  its evaluation/row-lock order. Do not weaken FOR UPDATE to NO KEY UPDATE.
- Establish SQLite's physical transaction/reservation state; Session transaction state
  alone is insufficient. Do not silently broaden locking for unrelated read callers.
- Preserve public/shared validator behavior, custom callbacks, exceptions and original
  transaction ownership without an extensive eligibility/fallback compatibility layer.
- Keep native private-grant comparisons transient and outside any new persisted/hash
  artifact. Identity, session, membership, paid, goal, privacy and clock checks remain.

No viable implementation satisfying all these obligations has yet been established.
The reviewed decision is to reject the reuse fast path, not to treat these requirements
as satisfied or to approve broader query skipping.

## Required Regression Package Before Adoption

Define exact tests on both SQLite and disposable PostgreSQL; a passing test on one
backend cannot substitute for the other. Capture baseline outputs/error descriptors
before editing product code. Proposed cause-specific cases:

1. **Scope query contract:** valid owned scope has seven baseline executions and exactly
   five after a qualified consolidation, with the five retained query predicates and
   lock modes unchanged. Repeated invocations requery afresh. Count at the DBAPI boundary
   without an observer that changes eligibility. No timing assertions in unit tests.
2. **No-N+1 characterization:** historical capture with zero, one and multiple facts
   retains five batch reads; canonical output equals the original saved value. Current
   graph/capture pins, reporting results and stored plan bytes remain identical.
3. **Error equivalence:** missing workspace/account/integration, inactive workspace or
   integration, foreign ownership, wrong provider/platform/native identity, duplicate
   source rows, changed generation and privacy yield the original failure descriptors
   in the original precedence. Include simultaneous invalid conditions.
4. **Observation boundaries:** inject source, privacy, workspace, session and membership
   changes between successive scope invocations and around media/authorization callbacks.
   Currentness or final publication must refuse and roll back; no prior value may replay.
5. **Same-session/event behavior:** dirty/new/deleted ORM state, autoflush, refresh/load
   events, raw SQL between retained statements, replaced validation callbacks, nested or
   replaced transactions, rollback and swallowed callback errors preserve old behavior
   or explicitly refuse before acceptance. Never silently suppress a callback.
6. **Membership and parents:** insert/delete selected facts, change referenced campaign
   ownership/native mapping, replace/delete historical selection or completion, and
   delete a capture or completion parent. Preserve complete membership checks, expected
   FK refusal/cascade semantics, and rollback restoration on both databases.
7. **Contention:** independent PostgreSQL writer contends on the original workspace,
   account/integration and native locks; committed changes before acquisition are seen.
   SQLite verifies physical BEGIN IMMEDIATE where required, conflicting writer refusal
   and ordinary read-transaction behavior. No sleep-based race oracle.
8. **Configured workflow:** after deterministic query/output tests and statics pass,
   qualify the actual HTTP/browser fixture with a new reviewed manifest. Separately
   measure whole-save improvement without renewing identity facts or moving expiry.

A limited baseline characterization was subsequently implemented in
`tests/test_selected_scope_query_contracts.py` and qualified on both databases. Its
four cases use actual zero/one-fact selected-acquisition fixtures, then repeat each
historical read and scope check three times. All pass with exactly five and seven
executions respectively, unchanged canonical output, original active caller transaction
and clean ORM state. The counting listener also rejects any non-SELECT execution.
This is not maximum-cardinality, contention or full persisted-state equivalence proof.
The broader adversarial cases above remain requirements for a viable optimization.

Baseline evidence: `/workspace/inlet-evidence/20261012/selected-scope-query02`, manifest
`c0d9fbfc835dcfb3ad5f44215b2480d6be1c439ac064dcc38ac468072f0d433b`.
Four exact pytest nodes passed (SQLite/PostgreSQL × None/10), each original exit 0 with
exact clean XML, verified source hashes and no process-cleanup survivors. Ruff, mypy
(1,598 source files), exact-node collection and whitespace checks all passed. Source
preflight and the minor test correction were independently reviewed. No application
source changed.

Attempt `selected-scope-query01` is preserved: Ruff passed; mypy stopped on an assertion
using the return of a function declared None; collection and all backend tests remained
unrun. Replacing that assertion with the ordinary function call preserves the query
oracle. Fresh attempt 02 reran the changed test's qualification; no failed case was
silently relabeled or retried unchanged.

## Durable State And Next Package

Next package is the scoped-query consolidation design and its baseline characterization,
not decoder caching, a blanket transaction cache or 49 new guard migrations. Stop the
candidate if its proof/compatibility cost remains disproportionate to the measured gain;
continue independent backlog work without claiming a timing fix.

HTTP qualification remains 57 passed / 1 unresolved; INLET-REL-20261012-01 remains open.
V3 remains default; V6/V7 remain release-unqualified. Migration 0094, retention semantics,
original failed evidence and all execution/release holds remain unchanged. No live,
provider, credential, spend, advertising, push, PR, hosted-CI, merge or deployment action.
