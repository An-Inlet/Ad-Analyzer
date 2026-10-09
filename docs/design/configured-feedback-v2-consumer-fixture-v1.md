# Configured Feedback V2 — Exact Eight-Case Consumer Interface

Proposal only, following configured-runtime checkpoint7a90f74. No implementation or
new test run in this document. Root review precedes adaptation. No production changes,
aggregate, advertising writes, live calls or changes to historical producers.

## Selected Original Failures

The frozen W1 failed-nodes.json selects exactly:

```text
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[sqlite-session]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[sqlite-generation]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[sqlite-expiry]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[sqlite-baseline]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[postgres-session]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[postgres-generation]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[postgres-expiry]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[postgres-baseline]
```

These remain the original function name/decorator and session, generation, expiry,
baseline matrix on SQLite/PostgreSQL. No new failure-credit identities or skipped
cases. Configured runtime10 is predecessor evidence, not eight-case closure.

## Exact Fixture Adaptation

Only tests/test_reported_feedback_configured_v2.py changes setup plumbing:

- Import configured_journey from tests.configured_planning_read_fixture.
- Use reviewed file-backed customer_engine wrapper, base_customer_engine fixture,
  and whole-test planning_origin fixture/PlanningOrigin annotation.
- Pass origin=planning_origin to the unchanged ten-value helper signature.
- Leave the entire original consumer body after the helper return unchanged.

No helper, shared old planning_runtime_fixture, production runtime, policy, source,
auth, TTL or browser changes. Actual relative original, ordinary same-actor login,
configured API factory/scheduler/GET acquisition, canonical profile and operating
policy, current preparation/PlanningConsent and V2 baseline are precisely7a90f74.
ExpectedPlanningConfirmation continues through final invalidation, ensuring original
financial graph/counters/ledger unchanged and no execution consent on the new draft.
Actual current native recorder remains separate from original scalar POST1.

## Current Assertions And Boundary

The existing test follows the real configured route chain, without runtime/policy
dependency overrides (ordinary replicas identity/DB plumbing remains):

1. GET reported-feedback/options exposes the actual initial V2 baseline ID.
2. GET comparisons/{actual-job-id} constructs the current comparison through API.
3. POST previews with exact returned comparison and baseline IDs creates a changed
   preview from46m, spending_authority none, review unavailable, and exact configured
   feedback policy digest. Do not substitute phase3's injected46m→47m feedback mapping.
4. Repeat POST must return identical content; GET preview exact content.
5. Actual ReportedFeedbackSlot dependency validation and existing lifecycle serializer
   return the exact document and omit original_session_digest.
6. Feedback creation, replay, read, validation and export add no native requests.
7. Preserve actual provider revocation, source generation increment, real baseline
   PreviewRow deletion, or existing+301sec configured clock advance. Subsequent GET
   must deny401/403/404/409 without adding native I/O.

The original assertion only requires a changed amount rather than exact45.75m;
retain it verbatim. The configured policy itself remains unchanged, and the separate
browser contract's45.75m expectation is not silently replaced by a new value.

Deleting the baseline is an intentional current dependency/privacy test, not deletion
of the strict planning confirmation. If actual cascades unexpectedly change protected
confirmation/financial rows, preserve the error and seek review; do not broaden the
finalizer. Likewise any actual period/profile/consent mismatch must not be replaced
by an early-denial expectation or an injected factory.

## Qualification

Run the actual session-mode cases first on both databases as a bounded gate, then the
exact8. Preserve failures, complete raw logs/XML, original identity map and AST proof
that every existing assertion/decorator remains unchanged. Current configured-runtime
positive2 and relevant strict planning confirmation/configuration tests form bounded
overlapping compatibility; they add no original failure credit. Whole Ruff, bare mypy
with isolated/tmp cache and diff check are required before code freeze. Isolated owned
SQLite files/PG schemas only; no aggregate or source/database resets.

## Browser Two Remain Deferred

`tests/test_reported_feedback_configured_browser.py::test_configured_v2_browser`
[sqlite/postgres] still consumes the old shared helper and hardcoded rotation subject.
A later separately reviewed adaptation must use the actual retained actor's subject
for same-owner rotation, transfer the actual job-owning cookie into real TLS Chromium,
retain exact configured45.75m UI assertion and late-response/session fencing. This
proposal neither edits its driver nor qualifies those two original identities.
