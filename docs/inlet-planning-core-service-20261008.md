# Planning Core Service — Qualification In Progress

Worktree `/workspace/inlet-plan-persistence`, branch
`codex/inlet-plan-persistence-current`. Reviewed reader repair e389d49 is preserved
as9df33a1. Public seam843e970/read-projection92c6875 are independently closed.

Current uncommitted modules: `input_resolution.py`, `repository.py`, `service.py`;
tests `test_planning_document_repository.py`. All frozen public methods are present.
No live/provider/model call or advertising write was performed.

Executed local checks before retained-source hooks were connected:

- Actual confirmed-goal input create/replay/CAS/rollback and PostgreSQL independent
  same-key creation/different-key revision races:3passed,1expected SQLite race skip.
- Input intent derivation and explicit unresolved selection rejection:2passed.
- Actual owned source MockHTTP create → generate → immutable history/replay for
  Google, Meta, TikTok on SQLite/PostgreSQL:6passed. Exact replay made no new
  native calls.
- Same6cases extended with independent decision/manual report/retraction chains,
  stale event sequence rejection, pagination and exact request-result replay:
  6passed.
- Session revoked after actual source reads:2passed; zero versions/dependencies,
  unchanged version head, only preexisting create receipt remained.
- No-op catalog reread:2passed; exact same entity/canonical key but different
  snapshot selection key. Therefore target-bearing inputs explicitly409 after
  current owner authorization, pending separately reviewed0088catalog receipts.
  No silent canonical-key remapping. Existing successful replay precedes this gate.

Latest whole Ruff and diff checks pass. Mypy1041 passed before retained-source
hook imports. Do not report current WIP as qualified: `retained_sources.py` is owned
by the evidence lane and must be integrated/reviewed before imports/final tests.
Capture/recheck use frozen f68914f interface. Capture runs after generation's
actual bundle recheck; complete dependency set is checked for reads/events.
Current source failures are explicit stale projections or409, never current.
Final original identity/session and fixed5second authority check remains after
all source work; read expiry is resampled after source checks.

Remaining: integrate frozen retained source implementation; run combined core
cohort plus current-read/export/source-change and ownership/role/adverse/race
regressions; independent review; commit core package for root API integration.
Target-bearing input/generation qualification remains separately blocked on
server-retained catalog receipts, not on a permission request.

## Frozen Core Package

The earlier pending record above is retained as chronology. Retained proof is now
integrated (interface c64992c, implementation9300fc6/a431fc8 independently closed).
All public service methods are implemented in `PlanningDocumentService`, using the
server-owned descriptive composer, owned read adapter, scoped immutable storage,
complete local source witness sets, current authority and atomic request receipts.
No client document or TargetRef serves as owned proof.

Final combined command:

```
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true /workspace/inlet-venv/bin/pytest -q -o addopts='' tests/test_planning_document_repository.py tests/test_planning_assertion_intent.py tests/test_planning_document_responses.py
```

Result: **31 passed,3 expected SQLite concurrency skips in44.42s**. PostgreSQL
runs actual independent-session same-key/different-key generation and withdrawal
races. The source fixtures use actual configured Google/Meta/TikTok readers with
MockHTTP; no execution records are seeded and no external provider is contacted.
Includes current/read/export/viewer access, no-native-IO retained reads, owner-only
mutations, cross-scope denial, exact request replay, stale binding409, draft goal409,
malformed assertion request validation, revoked-during-IO rollback, and final
cross-plan revision receipt protection.

Only withdrawal of the exact current manual-report event chain may target retained
historical versions after a newer version or observation expiry. It still requires
current owner/session, exact document/action/family/prior-event binding and current
global event CAS; it never creates a new accepted/applied assertion. Privacy-erased,
foreign, viewer, revoked, obsolete-chain and competing corrections are denied.
Expiry withdrawal tests inject the service clock beyond the actual saved deadline;
they do not change production deadlines or claim a real elapsed-time experiment.

Root-approved target-based planning remains explicitly409 pending0088receipt
storage and exact original-catalog reuse. No-target plans include bounded independent
all-unallocated scenario intents. Expert recommendation quality, live provider
behavior and the complete customer API/browser journey are not qualified by this
core package. Root API/controller integration and receipt package remain next.
